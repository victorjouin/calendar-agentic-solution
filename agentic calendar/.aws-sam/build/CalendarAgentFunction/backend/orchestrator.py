"""
orchestrator.py — Agent Orchestrator and PreferenceService.

Responsibilities:
- Maintain in-session conversation history
- Receive user message + session state, invoke Bedrock for intent resolution
- Route resolved intent to CalendarClient operations
- Handle ambiguity (present options, await user selection)
- Apply confirmation mode before write/delete actions
- Detect and apply user preference changes (working hours, confirmation mode, buffer)
- Format final reply and return updated session state
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.auth_manager import AuthManager, ReAuthRequiredException
from backend.bedrock_client import BedrockClient
from backend.calendar_client import CalendarClient
from backend.models import (
    BedrockResponse,
    CalendarEvent,
    CalendarEventInput,
    SessionState,
)
from backend import config

logger = logging.getLogger(__name__)


# ── Preference Detection Patterns ─────────────────────────────────────────────

_WORKING_HOURS_PATTERN = re.compile(
    r"(?:my\s+)?working\s+hours?\s+(?:are|is)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|-)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
    re.IGNORECASE,
)
_CONFIRMATION_OFF_PATTERN = re.compile(
    r"(?:stop|don'?t|do\s+not)\s+(?:asking?\s+(?:me\s+)?(?:to\s+)?confirm|confirm)",
    re.IGNORECASE,
)
_CONFIRMATION_ON_PATTERN = re.compile(
    r"(?:always|please)\s+(?:ask|confirm)\s+(?:before|me)",
    re.IGNORECASE,
)
_BUFFER_PATTERN = re.compile(
    r"(?:add|use|set)?\s*(\d+)\s*(?:-\s*)?minute\s+buffer",
    re.IGNORECASE,
)


class Orchestrator:
    """Orchestrates a complete conversation turn end-to-end."""

    def __init__(
        self,
        bedrock_client: Optional[BedrockClient] = None,
        calendar_client: Optional[CalendarClient] = None,
        auth_manager: Optional[AuthManager] = None,
    ) -> None:
        self._auth = auth_manager or AuthManager()
        self._bedrock = bedrock_client or BedrockClient()
        self._calendar = calendar_client or CalendarClient(auth_manager=self._auth)

    # ── Public API ────────────────────────────────────────────────────────────

    def process_message(
        self, message: str, session_state: SessionState
    ) -> tuple[str, SessionState]:
        """
        Main orchestration method — interprets user intent, dispatches action,
        returns the agent reply and updated session state.

        Args:
            message: The user's current message.
            session_state: Current session state.

        Returns:
            Tuple of (agent reply string, updated session state).
        """
        # Step 1: Detect and apply preference changes before invoking Bedrock
        session_state = self.update_session_preferences(message, session_state)

        # Step 2: Check if this message resolves a pending disambiguation
        if session_state.pending_action:
            reply, session_state = self._resolve_pending_action(message, session_state)
            session_state = self._append_to_history(message, reply, session_state)
            return reply, session_state

        # Step 3: Invoke Bedrock to resolve intent
        try:
            bedrock_response: BedrockResponse = self._bedrock.invoke(
                conversation_history=session_state.conversation_history,
                user_message=message,
                session_state=session_state,
            )
        except RuntimeError as exc:
            reply = str(exc)
            session_state = self._append_to_history(message, reply, session_state)
            return reply, session_state

        # Step 4: Route by action
        try:
            reply = self._route(bedrock_response, session_state)
        except ReAuthRequiredException:
            reply = (
                "Your Google Calendar session has expired. "
                "Please sign in again to continue."
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error executing action '%s': %s", bedrock_response.action, exc)
            reply = (
                f"Something went wrong while processing your request: {exc}. "
                "Please try again."
            )

        session_state = self._append_to_history(message, reply, session_state)
        return reply, session_state

    def resolve_ambiguity(
        self, matches: list[CalendarEvent], action: str
    ) -> str:
        """
        Format a disambiguation prompt when multiple events match a user request.
        Does NOT execute any action — returns a prompt string only.

        Args:
            matches: List of matching CalendarEvent objects.
            action: The requested action (e.g. "delete", "update").

        Returns:
            Formatted string presenting numbered options to the user.
        """
        lines = [
            f"I found {len(matches)} events that could match your request. "
            f"Which one would you like to {action}?\n"
        ]
        for i, event in enumerate(matches, start=1):
            day = event.start.strftime("%A, %d %b")
            time_range = f"{event.start.strftime('%H:%M')}–{event.end.strftime('%H:%M')}"
            lines.append(f"  {i}. **{event.title}** — {day} {time_range}")
        lines.append("\nPlease reply with the number of the event.")
        return "\n".join(lines)

    def apply_confirmation(
        self, action_description: str, session_state: SessionState
    ) -> str:
        """
        Return a confirmation prompt if confirmation mode is on, or empty string if off.

        Args:
            action_description: Human-readable description of the action to confirm.
            session_state: Current session state.

        Returns:
            Confirmation prompt string (non-empty) or empty string (execute immediately).
        """
        if not session_state.confirmation_mode:
            return ""
        return f"Just to confirm — shall I go ahead and {action_description}? (yes / no)"

    def update_session_preferences(
        self, message: str, session_state: SessionState
    ) -> SessionState:
        """
        Detect and apply user preference changes expressed in natural language.

        Handles:
        - Working hours ("My working hours are 8am to 5pm")
        - Confirmation mode ("Stop asking me to confirm")
        - Buffer time ("Add 15 minute buffer")

        Args:
            message: The user's current message.
            session_state: Current session state.

        Returns:
            Updated session state (may be unchanged if no preference detected).
        """
        # Working hours
        wh_match = _WORKING_HOURS_PATTERN.search(message)
        if wh_match:
            start_h = int(wh_match.group(1))
            start_m = int(wh_match.group(2) or 0)
            start_meridiem = (wh_match.group(3) or "").lower()
            end_h = int(wh_match.group(4))
            end_m = int(wh_match.group(5) or 0)
            end_meridiem = (wh_match.group(6) or "").lower()

            # Apply AM/PM conversion
            if start_meridiem == "pm" and start_h < 12:
                start_h += 12
            elif start_meridiem == "am" and start_h == 12:
                start_h = 0
            if end_meridiem == "pm" and end_h < 12:
                end_h += 12
            elif end_meridiem == "am" and end_h == 12:
                end_h = 0

            from datetime import time as dt_time
            session_state.working_hours_start = dt_time(start_h, start_m)
            session_state.working_hours_end = dt_time(end_h, end_m)
            logger.info(
                "Working hours updated to %02d:%02d–%02d:%02d",
                start_h, start_m, end_h, end_m,
            )

        # Confirmation mode — off
        if _CONFIRMATION_OFF_PATTERN.search(message):
            session_state.confirmation_mode = False
            logger.info("Confirmation mode disabled")

        # Confirmation mode — on
        elif _CONFIRMATION_ON_PATTERN.search(message):
            session_state.confirmation_mode = True
            logger.info("Confirmation mode enabled")

        # Buffer time
        buf_match = _BUFFER_PATTERN.search(message)
        if buf_match:
            session_state.buffer_minutes = int(buf_match.group(1))
            logger.info("Buffer time updated to %d minutes", session_state.buffer_minutes)

        return session_state

    # ── Routing ───────────────────────────────────────────────────────────────

    def _route(self, response: BedrockResponse, session_state: SessionState) -> str:
        """Route a resolved Bedrock intent to the appropriate handler."""
        action = response.action
        params = response.parameters

        if action == "read":
            return self._handle_read(params, session_state)
        if action == "create":
            return self._handle_create(params, response.reply, session_state)
        if action == "update":
            return self._handle_update(params, response.reply, session_state)
        if action == "delete":
            return self._handle_delete(params, response.reply, session_state)
        if action == "suggest_slots":
            return self._handle_suggest_slots(params, session_state)
        if action == "set_preference":
            return response.reply  # Preference already applied in update_session_preferences
        if action in ("clarify", "chat"):
            return response.reply

        logger.warning("Unhandled action '%s' — returning model reply", action)
        return response.reply

    # ── Action Handlers ───────────────────────────────────────────────────────

    def _handle_read(self, params: dict, session_state: SessionState) -> str:
        """Fetch and format calendar events for the requested time range."""
        time_range = params.get("time_range", "today")
        time_min, time_max = self._parse_time_range(time_range)

        events = self._calendar.list_events(time_min, time_max, session_state)

        if not events:
            return f"You have no events scheduled for {time_range}."

        lines = [f"Here's what you have for **{time_range}**:\n"]
        conflicts: list[str] = []

        for i, event in enumerate(events):
            day = event.start.strftime("%A, %d %b")
            time_str = f"{event.start.strftime('%H:%M')}–{event.end.strftime('%H:%M')}"
            recurring_tag = " 🔁" if event.is_recurring else ""
            lines.append(f"• **{event.title}**{recurring_tag} — {day} {time_str}")

            # Detect conflict with next event
            if i + 1 < len(events):
                next_event = events[i + 1]
                if event.end > next_event.start:
                    conflicts.append(
                        f"⚠️ **Conflict**: {event.title} overlaps with {next_event.title}"
                    )
                elif (next_event.start - event.end).total_seconds() < session_state.buffer_minutes * 60:
                    conflicts.append(
                        f"⚡ **Back-to-back**: {event.title} and {next_event.title} "
                        f"have less than {session_state.buffer_minutes} min between them"
                    )

        if conflicts:
            lines.append("\n" + "\n".join(conflicts))

        return "\n".join(lines)

    def _handle_create(
        self, params: dict, model_reply: str, session_state: SessionState
    ) -> str:
        """Create a new calendar event, applying confirmation if needed."""
        title = params.get("title", "New Event")
        duration = int(params.get("duration_minutes", 60))
        exact_start = params.get("exact_start")
        recurrence = params.get("recurrence")

        if exact_start:
            start_dt = datetime.fromisoformat(exact_start)
            end_dt = start_dt + timedelta(minutes=duration)
            event_input = CalendarEventInput(
                title=title,
                start=start_dt,
                end=end_dt,
                recurrence=recurrence,
            )
            action_desc = (
                f"create **{title}** on {start_dt.strftime('%A, %d %b at %H:%M')}"
                + (" (recurring)" if recurrence else "")
            )
            confirmation = self.apply_confirmation(action_desc, session_state)
            if confirmation:
                session_state.pending_action = {
                    "type": "create",
                    "event_input": {
                        "title": title,
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                        "recurrence": recurrence,
                    },
                }
                return confirmation

            created = self._calendar.create_event(event_input, session_state)
            return (
                f"Done! I've created **{created.title}** on "
                f"{created.start.strftime('%A, %d %b at %H:%M')}."
            )

        # No exact time — suggest slots first
        return self._handle_suggest_slots(params, session_state)

    def _handle_suggest_slots(self, params: dict, session_state: SessionState) -> str:
        """Find and present free time slots for the user to choose from."""
        duration = int(params.get("duration_minutes", 60))
        window = params.get("preferred_window", "this week")
        time_min, time_max = self._parse_time_range(window)

        slots = self._calendar.find_free_slots(duration, time_min, time_max, session_state)

        if not slots:
            return (
                f"I couldn't find any free {duration}-minute slots in your working hours "
                f"for {window}. Would you like me to look at a different time window?"
            )

        lines = [
            f"Here are {len(slots)} available slot{'s' if len(slots) > 1 else ''} "
            f"for a {duration}-minute block:\n"
        ]
        for i, slot in enumerate(slots, start=1):
            lines.append(
                f"  {i}. {slot.start.strftime('%A, %d %b %H:%M')}–"
                f"{slot.end.strftime('%H:%M')} — {slot.rationale}"
            )
        lines.append(
            "\nReply with the number of your preferred slot, or ask me to look elsewhere."
        )

        # Store pending create context so we can create the event once user picks a slot
        session_state.pending_action = {
            "type": "pick_slot",
            "title": params.get("title", "New Event"),
            "duration_minutes": duration,
            "recurrence": params.get("recurrence"),
            "slots": [
                {"start": s.start.isoformat(), "end": s.end.isoformat()} for s in slots
            ],
        }

        return "\n".join(lines)

    def _handle_update(
        self, params: dict, model_reply: str, session_state: SessionState
    ) -> str:
        """Reschedule an existing event."""
        event_desc = params.get("event_description", "")
        new_time = params.get("new_time", "")

        # Find matching events
        now = datetime.now(tz=timezone.utc)
        events = self._calendar.list_events(now, now + timedelta(days=14), session_state)
        matches = self._find_matching_events(event_desc, events)

        if not matches:
            return f"I couldn't find an event matching '{event_desc}'. Could you be more specific?"

        if len(matches) > 1:
            reply = self.resolve_ambiguity(matches, "reschedule")
            session_state.pending_action = {
                "type": "update_disambiguate",
                "matches": [e.event_id for e in matches],
                "new_time": new_time,
            }
            return reply

        event = matches[0]
        action_desc = (
            f"reschedule **{event.title}** to {new_time}"
        )
        confirmation = self.apply_confirmation(action_desc, session_state)
        if confirmation:
            session_state.pending_action = {
                "type": "update",
                "event_id": event.event_id,
                "new_time": new_time,
                "title": event.title,
            }
            return confirmation

        return self._execute_update(event.event_id, event, new_time, session_state)

    def _handle_delete(
        self, params: dict, model_reply: str, session_state: SessionState
    ) -> str:
        """Delete a calendar event."""
        event_desc = params.get("event_description", "")

        now = datetime.now(tz=timezone.utc)
        events = self._calendar.list_events(now, now + timedelta(days=14), session_state)
        matches = self._find_matching_events(event_desc, events)

        if not matches:
            return f"I couldn't find an event matching '{event_desc}'. Could you be more specific?"

        if len(matches) > 1:
            reply = self.resolve_ambiguity(matches, "cancel")
            session_state.pending_action = {
                "type": "delete_disambiguate",
                "matches": [e.event_id for e in matches],
                "match_titles": [e.title for e in matches],
            }
            return reply

        event = matches[0]
        action_desc = (
            f"cancel **{event.title}** on {event.start.strftime('%A, %d %b at %H:%M')}"
        )
        confirmation = self.apply_confirmation(action_desc, session_state)
        if confirmation:
            session_state.pending_action = {
                "type": "delete",
                "event_id": event.event_id,
                "title": event.title,
            }
            return confirmation

        self._calendar.delete_event(event.event_id, session_state)
        return f"Done! I've cancelled **{event.title}**."

    # ── Pending Action Resolution ─────────────────────────────────────────────

    def _resolve_pending_action(
        self, message: str, session_state: SessionState
    ) -> tuple[str, SessionState]:
        """Handle a user reply that resolves a pending confirmation or disambiguation."""
        pending = session_state.pending_action
        action_type = pending.get("type", "")
        msg_lower = message.strip().lower()

        # ── Confirmation responses ────────────────────────────────────────────
        if action_type in ("create", "update", "delete"):
            if msg_lower in ("yes", "y", "confirm", "ok", "sure", "go ahead", "do it"):
                session_state.pending_action = None
                return self._execute_confirmed_action(pending, session_state), session_state
            else:
                session_state.pending_action = None
                return "No problem — I've cancelled that action.", session_state

        # ── Slot selection ────────────────────────────────────────────────────
        if action_type == "pick_slot":
            try:
                choice = int(msg_lower) - 1
                slots = pending["slots"]
                if 0 <= choice < len(slots):
                    slot = slots[choice]
                    start_dt = datetime.fromisoformat(slot["start"])
                    end_dt = datetime.fromisoformat(slot["end"])
                    event_input = CalendarEventInput(
                        title=pending.get("title", "New Event"),
                        start=start_dt,
                        end=end_dt,
                        recurrence=pending.get("recurrence"),
                    )
                    action_desc = (
                        f"create **{event_input.title}** on "
                        f"{start_dt.strftime('%A, %d %b at %H:%M')}"
                    )
                    confirmation = self.apply_confirmation(action_desc, session_state)
                    if confirmation:
                        session_state.pending_action = {
                            "type": "create",
                            "event_input": {
                                "title": event_input.title,
                                "start": start_dt.isoformat(),
                                "end": end_dt.isoformat(),
                                "recurrence": event_input.recurrence,
                            },
                        }
                        return confirmation, session_state

                    session_state.pending_action = None
                    created = self._calendar.create_event(event_input, session_state)
                    return (
                        f"Done! I've created **{created.title}** on "
                        f"{created.start.strftime('%A, %d %b at %H:%M')}.",
                        session_state,
                    )
                else:
                    return (
                        f"Please reply with a number between 1 and {len(slots)}.",
                        session_state,
                    )
            except ValueError:
                return (
                    "Please reply with the number of the slot you'd like (e.g. '1', '2').",
                    session_state,
                )

        # ── Disambiguation responses ──────────────────────────────────────────
        if action_type in ("delete_disambiguate", "update_disambiguate"):
            try:
                choice = int(msg_lower) - 1
                matches = pending["matches"]
                if 0 <= choice < len(matches):
                    event_id = matches[choice]
                    session_state.pending_action = None
                    if action_type == "delete_disambiguate":
                        title = pending.get("match_titles", ["the event"])[choice]
                        action_desc = f"cancel **{title}**"
                        confirmation = self.apply_confirmation(action_desc, session_state)
                        if confirmation:
                            session_state.pending_action = {
                                "type": "delete",
                                "event_id": event_id,
                                "title": title,
                            }
                            return confirmation, session_state
                        self._calendar.delete_event(event_id, session_state)
                        return f"Done! I've cancelled **{title}**.", session_state
                    else:
                        new_time = pending.get("new_time", "")
                        return (
                            self._execute_update(event_id, None, new_time, session_state),
                            session_state,
                        )
                else:
                    return (
                        f"Please reply with a number between 1 and {len(matches)}.",
                        session_state,
                    )
            except ValueError:
                return (
                    "Please reply with the number of the event you meant (e.g. '1', '2').",
                    session_state,
                )

        # Unknown pending action — clear it
        session_state.pending_action = None
        return "Sorry, I lost track of what we were doing. Could you repeat your request?", session_state

    def _execute_confirmed_action(
        self, pending: dict, session_state: SessionState
    ) -> str:
        """Execute a previously confirmed action."""
        action_type = pending["type"]

        if action_type == "create":
            ei = pending["event_input"]
            event_input = CalendarEventInput(
                title=ei["title"],
                start=datetime.fromisoformat(ei["start"]),
                end=datetime.fromisoformat(ei["end"]),
                recurrence=ei.get("recurrence"),
            )
            created = self._calendar.create_event(event_input, session_state)
            return (
                f"Done! I've created **{created.title}** on "
                f"{created.start.strftime('%A, %d %b at %H:%M')}."
            )

        if action_type == "delete":
            self._calendar.delete_event(pending["event_id"], session_state)
            return f"Done! I've cancelled **{pending['title']}**."

        if action_type == "update":
            return self._execute_update(
                pending["event_id"], None, pending["new_time"], session_state
            )

        return "Action completed."

    def _execute_update(
        self,
        event_id: str,
        event: Optional[CalendarEvent],
        new_time: str,
        session_state: SessionState,
    ) -> str:
        """Parse new_time and execute the update via CalendarClient."""
        # For MVP, new_time is a natural language string — we ask Bedrock to parse it
        # In a full implementation this would use a dedicated time parser
        # Here we do a best-effort parse
        try:
            new_start = self._parse_natural_time(new_time)
        except ValueError:
            return (
                f"I understood you want to reschedule, but I couldn't parse '{new_time}' "
                "as a time. Could you be more specific? (e.g. 'Friday at 2pm')"
            )

        # Preserve original duration if we have the event
        if event:
            duration = int((event.end - event.start).total_seconds() / 60)
        else:
            duration = 60  # Default 1 hour

        new_end = new_start + timedelta(minutes=duration)
        from backend.models import CalendarEventInput
        updates = CalendarEventInput(title="", start=new_start, end=new_end)
        updated = self._calendar.update_event(event_id, updates, session_state)
        return (
            f"Done! I've rescheduled **{updated.title}** to "
            f"{updated.start.strftime('%A, %d %b at %H:%M')}."
        )

    # ── Utility Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _append_to_history(
        user_message: str, assistant_reply: str, session_state: SessionState
    ) -> SessionState:
        """Append the current turn to the conversation history."""
        session_state.conversation_history.append(
            {"role": "user", "content": user_message}
        )
        session_state.conversation_history.append(
            {"role": "assistant", "content": assistant_reply}
        )
        return session_state

    @staticmethod
    def _find_matching_events(
        description: str, events: list[CalendarEvent]
    ) -> list[CalendarEvent]:
        """
        Find events whose title or time matches the user's description.
        Simple substring match — Bedrock handles the semantic understanding.
        """
        desc_lower = description.lower()
        return [
            e for e in events
            if desc_lower in e.title.lower()
            or e.start.strftime("%H:%M").lower() in desc_lower
            or e.start.strftime("%I%p").lower().lstrip("0") in desc_lower
        ]

    @staticmethod
    def _parse_time_range(time_range: str) -> tuple[datetime, datetime]:
        """
        Parse a time range string into (time_min, time_max) UTC datetimes.
        Supports: today, tomorrow, this_week, next_week, or ISO date range.
        """
        now = datetime.now(tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        tr = time_range.lower().replace(" ", "_")

        if tr in ("today", "today's"):
            return now, now + timedelta(days=1)
        if tr in ("tomorrow", "tomorrow's"):
            return now + timedelta(days=1), now + timedelta(days=2)
        if tr in ("this_week", "the_week"):
            # Monday to Sunday of current week
            monday = now - timedelta(days=now.weekday())
            return monday, monday + timedelta(days=7)
        if tr == "next_week":
            monday = now - timedelta(days=now.weekday()) + timedelta(weeks=1)
            return monday, monday + timedelta(days=7)
        if "afternoon" in tr:
            base = now + timedelta(days=1) if "tomorrow" in tr else now
            return base.replace(hour=12), base.replace(hour=18)
        if "morning" in tr:
            base = now + timedelta(days=1) if "tomorrow" in tr else now
            return base.replace(hour=6), base.replace(hour=12)
        if "evening" in tr:
            base = now + timedelta(days=1) if "tomorrow" in tr else now
            return base.replace(hour=17), base.replace(hour=21)

        # Default: next 7 days
        return now, now + timedelta(days=7)

    @staticmethod
    def _parse_natural_time(time_str: str) -> datetime:
        """
        Best-effort parse of a natural language time string.
        Raises ValueError if parsing fails.
        """
        now = datetime.now(tz=timezone.utc)
        ts = time_str.lower().strip()

        # Try ISO format first
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            pass

        # Simple patterns
        day_offsets = {
            "today": 0, "tomorrow": 1,
            "monday": (0 - now.weekday()) % 7 or 7,
            "tuesday": (1 - now.weekday()) % 7 or 7,
            "wednesday": (2 - now.weekday()) % 7 or 7,
            "thursday": (3 - now.weekday()) % 7 or 7,
            "friday": (4 - now.weekday()) % 7 or 7,
            "saturday": (5 - now.weekday()) % 7 or 7,
            "sunday": (6 - now.weekday()) % 7 or 7,
        }

        base = now.replace(hour=9, minute=0, second=0, microsecond=0)
        for day_name, offset in day_offsets.items():
            if day_name in ts:
                base = base + timedelta(days=offset)
                break

        # Extract time component
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", ts, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = (time_match.group(3) or "").lower()
            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            return base.replace(hour=hour, minute=minute)

        return base


def create_new_session() -> SessionState:
    """Create a fresh SessionState with default preferences."""
    return SessionState(
        session_id=str(uuid.uuid4()),
        working_hours_start=config.DEFAULT_WORKING_HOURS_START,
        working_hours_end=config.DEFAULT_WORKING_HOURS_END,
        working_days=list(config.DEFAULT_WORKING_DAYS),
        buffer_minutes=config.DEFAULT_BUFFER_MINUTES,
        confirmation_mode=config.DEFAULT_CONFIRMATION_MODE,
    )
