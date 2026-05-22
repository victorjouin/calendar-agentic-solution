"""
models.py — Shared data models for the Calendar Agent backend.
All inter-module data exchange uses these typed dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional


# ── Calendar Models ───────────────────────────────────────────────────────────


@dataclass
class CalendarEvent:
    """A calendar event retrieved from Google Calendar."""

    event_id: str
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    # iCal RRULE string, e.g. "RRULE:FREQ=WEEKLY;BYDAY=MO"
    recurrence: Optional[str] = None
    is_recurring: bool = False


@dataclass
class CalendarEventInput:
    """Input data for creating or updating a calendar event."""

    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    # iCal RRULE string for recurring events; None for single events
    recurrence: Optional[str] = None


@dataclass
class TimeSlot:
    """A suggested available time slot."""

    start: datetime
    end: datetime
    # Human-readable explanation of why this slot was chosen
    rationale: str


# ── Bedrock Models ────────────────────────────────────────────────────────────

# Valid action types the Bedrock model can return
VALID_ACTIONS = frozenset(
    {
        "read",           # Fetch and summarise calendar events
        "create",         # Create a new event
        "update",         # Reschedule an existing event
        "delete",         # Delete an event
        "suggest_slots",  # Find and propose free time slots
        "set_preference", # Update a session preference (working hours, confirmation mode, etc.)
        "clarify",        # Agent needs more information before acting
        "chat",           # General conversational reply, no calendar action
    }
)


@dataclass
class BedrockResponse:
    """Parsed response from Amazon Bedrock."""

    # One of the VALID_ACTIONS values
    action: str
    # Action-specific parameters extracted by the model
    # e.g. {"title": "Team sync", "duration_minutes": 60, "window": "tomorrow afternoon"}
    parameters: dict
    # The natural language reply to show the user
    reply: str
    # True when the model cannot resolve the request without more information
    needs_clarification: bool = False


# ── OAuth Models ──────────────────────────────────────────────────────────────


@dataclass
class OAuthTokens:
    """Google OAuth 2.0 token set."""

    access_token: str
    refresh_token: str
    # UTC datetime when the access token expires
    expires_at: datetime


# ── Session State ─────────────────────────────────────────────────────────────


@dataclass
class SessionState:
    """
    All per-session state for a single conversation.

    This object is serialised to JSON and returned to the frontend on every
    response turn. The frontend stores it in memory and sends it back on the
    next request. There is no server-side session store.
    """

    session_id: str

    # Full conversation history for the current session.
    # Each entry: {"role": "user" | "assistant", "content": "<text>"}
    conversation_history: list[dict] = field(default_factory=list)

    # Working hours used when suggesting time slots
    working_hours_start: time = time(9, 0)
    working_hours_end: time = time(18, 0)
    # 0=Monday, 1=Tuesday, …, 4=Friday
    working_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])

    # Minimum gap between meetings when suggesting slots (minutes)
    buffer_minutes: int = 15

    # When True, agent asks for confirmation before every write/delete operation
    confirmation_mode: bool = True

    # Session-level event cache. Populated on first read, cleared on every write.
    event_cache: list[CalendarEvent] = field(default_factory=list)

    # Pending action awaiting user confirmation or disambiguation
    # Stored as a dict so it can be JSON-serialised
    pending_action: Optional[dict] = None
