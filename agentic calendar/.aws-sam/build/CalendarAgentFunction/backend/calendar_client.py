"""
calendar_client.py — Google Calendar API v3 integration.

Responsibilities:
- Execute all Google Calendar API operations (list, create, update, delete)
- Manage session-level in-memory event cache (populated on read, cleared on write)
- Implement exponential backoff on HTTP 429 rate limit responses
- Find available time slots respecting working hours and buffer preferences
- Delegate authentication to AuthManager
"""

from __future__ import annotations

import logging
import time as time_module
from datetime import datetime, timedelta, timezone
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from backend import config
from backend.auth_manager import AuthManager
from backend.models import (
    CalendarEvent,
    CalendarEventInput,
    SessionState,
    TimeSlot,
)

logger = logging.getLogger(__name__)


class CalendarClient:
    """Google Calendar API v3 client with session-level caching."""

    def __init__(self, auth_manager: Optional[AuthManager] = None) -> None:
        self._auth = auth_manager or AuthManager()

    # ── Public API ────────────────────────────────────────────────────────────

    def list_events(
        self,
        time_min: datetime,
        time_max: datetime,
        session_state: SessionState,
    ) -> list[CalendarEvent]:
        """
        Retrieve calendar events within a time range.
        Returns cached results if the cache is populated; fetches from Google otherwise.

        Args:
            time_min: Start of the time range (UTC).
            time_max: End of the time range (UTC).
            session_state: Current session state (for cache lookup and update).

        Returns:
            List of CalendarEvent objects within the requested range.
        """
        # Return from cache if available
        if session_state.event_cache:
            logger.debug("Returning %d events from session cache", len(session_state.event_cache))
            # Filter cache to the requested window
            return [
                e for e in session_state.event_cache
                if e.start >= time_min and e.end <= time_max
            ]

        service = self._get_service()
        raw_events = self._list_events_with_backoff(service, time_min, time_max)
        events = [self._parse_event(e) for e in raw_events]

        # Populate cache
        session_state.event_cache = events
        logger.info("Fetched %d events from Google Calendar and cached", len(events))
        return events

    def create_event(
        self,
        event_input: CalendarEventInput,
        session_state: SessionState,
    ) -> CalendarEvent:
        """
        Create a new calendar event (single or recurring).

        Args:
            event_input: Event details including optional recurrence rule.
            session_state: Current session state (cache will be invalidated).

        Returns:
            The created CalendarEvent with its Google-assigned event ID.
        """
        service = self._get_service()
        body = self._build_event_body(event_input)

        result = self._execute_with_backoff(
            service.events().insert(calendarId="primary", body=body)
        )

        event = self._parse_event(result)
        session_state.event_cache = []  # Invalidate cache
        logger.info("Created event '%s' (id=%s)", event.title, event.event_id)
        return event

    def update_event(
        self,
        event_id: str,
        updates: CalendarEventInput,
        session_state: SessionState,
    ) -> CalendarEvent:
        """
        Update an existing calendar event (used for rescheduling).

        Args:
            event_id: Google Calendar event ID.
            updates: Updated event fields.
            session_state: Current session state (cache will be invalidated).

        Returns:
            The updated CalendarEvent.
        """
        service = self._get_service()
        body = self._build_event_body(updates)

        result = self._execute_with_backoff(
            service.events().update(
                calendarId="primary", eventId=event_id, body=body
            )
        )

        event = self._parse_event(result)
        session_state.event_cache = []  # Invalidate cache
        logger.info("Updated event '%s' (id=%s)", event.title, event.event_id)
        return event

    def delete_event(self, event_id: str, session_state: SessionState) -> bool:
        """
        Delete a calendar event by its Google Calendar event ID.

        Args:
            event_id: Google Calendar event ID.
            session_state: Current session state (cache will be invalidated).

        Returns:
            True on success.
        """
        service = self._get_service()
        self._execute_with_backoff(
            service.events().delete(calendarId="primary", eventId=event_id)
        )
        session_state.event_cache = []  # Invalidate cache
        logger.info("Deleted event id=%s", event_id)
        return True

    def find_free_slots(
        self,
        duration_minutes: int,
        time_min: datetime,
        time_max: datetime,
        session_state: SessionState,
        max_suggestions: int = 3,
    ) -> list[TimeSlot]:
        """
        Find available time slots within a window, respecting working hours and buffer rules.

        Args:
            duration_minutes: Required event duration in minutes.
            time_min: Start of the search window (UTC).
            time_max: End of the search window (UTC).
            session_state: Current session state (working hours, buffer, event cache).
            max_suggestions: Maximum number of slots to return (default 3).

        Returns:
            List of up to max_suggestions TimeSlot objects.
        """
        events = self.list_events(time_min, time_max, session_state)
        busy_periods = [(e.start, e.end) for e in events]

        slots: list[TimeSlot] = []
        cursor = time_min

        while cursor < time_max and len(slots) < max_suggestions:
            # Align cursor to working hours
            cursor = self._next_working_time(cursor, session_state)
            if cursor >= time_max:
                break

            slot_end = cursor + timedelta(minutes=duration_minutes)

            # Ensure slot fits within working hours
            wh_end = cursor.replace(
                hour=session_state.working_hours_end.hour,
                minute=session_state.working_hours_end.minute,
                second=0,
                microsecond=0,
            )
            if slot_end > wh_end:
                # Move to next working day
                cursor = self._start_of_next_working_day(cursor, session_state)
                continue

            # Check for conflicts with existing events (including buffer)
            buffer = timedelta(minutes=session_state.buffer_minutes)
            conflict = any(
                not (slot_end + buffer <= busy_start or cursor - buffer >= busy_end)
                for busy_start, busy_end in busy_periods
            )

            if not conflict:
                rationale = self._build_slot_rationale(cursor, slot_end, busy_periods, session_state)
                slots.append(TimeSlot(start=cursor, end=slot_end, rationale=rationale))
                # Advance past this slot + buffer for the next search
                cursor = slot_end + buffer
            else:
                # Advance by 15 minutes and try again
                cursor += timedelta(minutes=15)

        return slots

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _get_service(self):
        """Build and return an authenticated Google Calendar API service."""
        access_token = self._auth.get_valid_access_token()
        credentials = Credentials(token=access_token)
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _list_events_with_backoff(
        self, service, time_min: datetime, time_max: datetime
    ) -> list[dict]:
        """Fetch raw event dicts from Google Calendar with exponential backoff."""
        request = service.events().list(
            calendarId="primary",
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=config.CALENDAR_MAX_RESULTS,
            singleEvents=True,
            orderBy="startTime",
        )
        return self._execute_with_backoff(request).get("items", [])

    def _execute_with_backoff(self, request):
        """Execute a Google API request with exponential backoff on HTTP 429."""
        delay = config.CALENDAR_BACKOFF_BASE_SECONDS
        for attempt in range(config.CALENDAR_MAX_RETRIES + 1):
            try:
                return request.execute()
            except HttpError as exc:
                if exc.resp.status == 429 and attempt < config.CALENDAR_MAX_RETRIES:
                    logger.warning(
                        "Google Calendar API rate limit hit — retrying in %.1fs (attempt %d/%d)",
                        delay,
                        attempt + 1,
                        config.CALENDAR_MAX_RETRIES,
                    )
                    time_module.sleep(delay)
                    delay *= 2
                else:
                    raise

    @staticmethod
    def _parse_event(raw: dict) -> CalendarEvent:
        """Convert a raw Google Calendar API event dict to a CalendarEvent."""
        start_raw = raw.get("start", {})
        end_raw = raw.get("end", {})

        # Events can be all-day (date) or timed (dateTime)
        start_str = start_raw.get("dateTime") or start_raw.get("date", "")
        end_str = end_raw.get("dateTime") or end_raw.get("date", "")

        def _parse_dt(s: str) -> datetime:
            if "T" in s:
                return datetime.fromisoformat(s)
            # All-day event — treat as midnight UTC
            return datetime.fromisoformat(s + "T00:00:00+00:00")

        recurrence = raw.get("recurrence")
        rrule = recurrence[0] if recurrence else None

        return CalendarEvent(
            event_id=raw.get("id", ""),
            title=raw.get("summary", "(No title)"),
            start=_parse_dt(start_str),
            end=_parse_dt(end_str),
            location=raw.get("location"),
            recurrence=rrule,
            is_recurring=bool(recurrence),
        )

    @staticmethod
    def _build_event_body(event_input: CalendarEventInput) -> dict:
        """Convert a CalendarEventInput to a Google Calendar API request body."""
        body: dict = {
            "summary": event_input.title,
            "start": {"dateTime": event_input.start.isoformat()},
            "end": {"dateTime": event_input.end.isoformat()},
        }
        if event_input.location:
            body["location"] = event_input.location
        if event_input.recurrence:
            body["recurrence"] = [event_input.recurrence]
        return body

    @staticmethod
    def _next_working_time(dt: datetime, session_state: SessionState) -> datetime:
        """
        Advance dt to the next valid working time.
        If dt is before working hours start, move to working hours start.
        If dt is after working hours end, move to start of next working day.
        If dt is on a non-working day, move to start of next working day.
        """
        wh_start = session_state.working_hours_start
        wh_end = session_state.working_hours_end

        # Move to next working day if today is not a working day
        while dt.weekday() not in session_state.working_days:
            dt = (dt + timedelta(days=1)).replace(
                hour=wh_start.hour, minute=wh_start.minute, second=0, microsecond=0
            )

        current_time = dt.time()

        if current_time < wh_start:
            return dt.replace(
                hour=wh_start.hour, minute=wh_start.minute, second=0, microsecond=0
            )

        if current_time >= wh_end:
            return CalendarClient._start_of_next_working_day(dt, session_state)

        return dt

    @staticmethod
    def _start_of_next_working_day(dt: datetime, session_state: SessionState) -> datetime:
        """Return the start of the next working day."""
        wh_start = session_state.working_hours_start
        next_day = dt + timedelta(days=1)
        next_day = next_day.replace(
            hour=wh_start.hour, minute=wh_start.minute, second=0, microsecond=0
        )
        while next_day.weekday() not in session_state.working_days:
            next_day += timedelta(days=1)
        return next_day

    @staticmethod
    def _build_slot_rationale(
        start: datetime,
        end: datetime,
        busy_periods: list[tuple[datetime, datetime]],
        session_state: SessionState,
    ) -> str:
        """Build a human-readable rationale for a suggested time slot."""
        day_name = start.strftime("%A")
        time_str = f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
        buffer = session_state.buffer_minutes

        # Check if there are nearby events
        nearby = [
            b for b in busy_periods
            if abs((b[0] - end).total_seconds()) <= buffer * 60 * 2
            or abs((start - b[1]).total_seconds()) <= buffer * 60 * 2
        ]

        if not nearby:
            return f"{day_name} {time_str} — clear slot with no adjacent meetings"
        return (
            f"{day_name} {time_str} — {buffer}-minute buffer maintained around adjacent meetings"
        )
