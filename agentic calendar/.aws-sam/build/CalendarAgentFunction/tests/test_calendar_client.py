"""
test_calendar_client.py — Unit tests for CalendarClient.

Google Calendar API calls and AuthManager are mocked throughout.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from backend.calendar_client import CalendarClient
from backend.models import CalendarEvent, CalendarEventInput, SessionState


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session() -> SessionState:
    from datetime import time
    return SessionState(
        session_id="test-session",
        working_hours_start=time(9, 0),
        working_hours_end=time(18, 0),
        working_days=[0, 1, 2, 3, 4],
        buffer_minutes=15,
        confirmation_mode=True,
    )


def _utc(year=2026, month=5, day=22, hour=10, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _raw_event(
    event_id="evt1",
    title="Team Sync",
    start_hour=10,
    end_hour=11,
    recurrence=None,
) -> dict:
    base = "2026-05-22"
    raw = {
        "id": event_id,
        "summary": title,
        "start": {"dateTime": f"{base}T{start_hour:02d}:00:00+00:00"},
        "end": {"dateTime": f"{base}T{end_hour:02d}:00:00+00:00"},
    }
    if recurrence:
        raw["recurrence"] = [recurrence]
    return raw


def _make_client() -> CalendarClient:
    mock_auth = MagicMock()
    mock_auth.get_valid_access_token.return_value = "fake-access-token"
    return CalendarClient(auth_manager=mock_auth)


# ── list_events ───────────────────────────────────────────────────────────────


class TestListEvents:
    def test_returns_cached_events_when_cache_populated(self):
        client = _make_client()
        session = _make_session()
        cached_event = CalendarEvent(
            event_id="cached",
            title="Cached Event",
            start=_utc(hour=10),
            end=_utc(hour=11),
        )
        session.event_cache = [cached_event]

        result = client.list_events(_utc(hour=9), _utc(hour=18), session)

        assert len(result) == 1
        assert result[0].event_id == "cached"

    def test_fetches_from_api_when_cache_empty(self):
        client = _make_client()
        session = _make_session()

        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {
            "items": [_raw_event()]
        }

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.list_events(_utc(hour=9), _utc(hour=18), session)

        assert len(result) == 1
        assert result[0].title == "Team Sync"
        assert len(session.event_cache) == 1  # Cache populated

    def test_populates_cache_after_fetch(self):
        client = _make_client()
        session = _make_session()
        assert len(session.event_cache) == 0

        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {
            "items": [_raw_event(), _raw_event(event_id="evt2", title="1:1")]
        }

        with patch.object(client, "_get_service", return_value=mock_service):
            client.list_events(_utc(hour=9), _utc(hour=18), session)

        assert len(session.event_cache) == 2


# ── create_event ──────────────────────────────────────────────────────────────


class TestCreateEvent:
    def test_creates_single_event(self):
        client = _make_client()
        session = _make_session()
        session.event_cache = [MagicMock()]  # Pre-populate cache

        event_input = CalendarEventInput(
            title="Deep Work",
            start=_utc(hour=14),
            end=_utc(hour=16),
        )

        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = _raw_event(
            event_id="new-evt", title="Deep Work", start_hour=14, end_hour=16
        )

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.create_event(event_input, session)

        assert result.title == "Deep Work"
        assert result.event_id == "new-evt"
        assert len(session.event_cache) == 0  # Cache invalidated

    def test_creates_recurring_event(self):
        client = _make_client()
        session = _make_session()

        event_input = CalendarEventInput(
            title="Weekly Sync",
            start=_utc(hour=10),
            end=_utc(hour=11),
            recurrence="RRULE:FREQ=WEEKLY;BYDAY=FR",
        )

        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = _raw_event(
            event_id="recur-evt",
            title="Weekly Sync",
            recurrence="RRULE:FREQ=WEEKLY;BYDAY=FR",
        )

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.create_event(event_input, session)

        assert result.is_recurring is True
        # Verify recurrence was included in the API call body
        insert_call = mock_service.events().insert.call_args
        body = insert_call[1]["body"]
        assert "recurrence" in body


# ── update_event ──────────────────────────────────────────────────────────────


class TestUpdateEvent:
    def test_updates_event_and_invalidates_cache(self):
        client = _make_client()
        session = _make_session()
        session.event_cache = [MagicMock()]

        updates = CalendarEventInput(
            title="Team Sync",
            start=_utc(hour=15),
            end=_utc(hour=16),
        )

        mock_service = MagicMock()
        mock_service.events().update().execute.return_value = _raw_event(
            event_id="evt1", title="Team Sync", start_hour=15, end_hour=16
        )

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.update_event("evt1", updates, session)

        assert result.start.hour == 15
        assert len(session.event_cache) == 0  # Cache invalidated


# ── delete_event ──────────────────────────────────────────────────────────────


class TestDeleteEvent:
    def test_deletes_event_and_invalidates_cache(self):
        client = _make_client()
        session = _make_session()
        session.event_cache = [MagicMock()]

        mock_service = MagicMock()
        mock_service.events().delete().execute.return_value = None

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.delete_event("evt1", session)

        assert result is True
        assert len(session.event_cache) == 0  # Cache invalidated
        # Verify delete was called with correct args (use call_args on the chained mock)
        mock_service.events.return_value.delete.assert_called_with(
            calendarId="primary", eventId="evt1"
        )


# ── find_free_slots ───────────────────────────────────────────────────────────


class TestFindFreeSlots:
    def test_finds_slot_in_empty_calendar(self):
        client = _make_client()
        session = _make_session()

        # Monday 2026-05-25, 9am–6pm
        time_min = datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc)
        time_max = datetime(2026, 5, 25, 18, 0, tzinfo=timezone.utc)

        with patch.object(client, "list_events", return_value=[]):
            slots = client.find_free_slots(60, time_min, time_max, session)

        assert len(slots) > 0
        assert slots[0].start >= time_min
        assert slots[0].end <= time_max

    def test_respects_buffer_between_meetings(self):
        client = _make_client()
        session = _make_session()
        session.buffer_minutes = 15

        # Existing event 10:00–11:00
        existing = CalendarEvent(
            event_id="e1",
            title="Meeting",
            start=datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc),
            end=datetime(2026, 5, 25, 11, 0, tzinfo=timezone.utc),
        )

        time_min = datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc)
        time_max = datetime(2026, 5, 25, 18, 0, tzinfo=timezone.utc)

        with patch.object(client, "list_events", return_value=[existing]):
            slots = client.find_free_slots(60, time_min, time_max, session)

        # No slot should start within 15 minutes of the existing event's end (11:00)
        for slot in slots:
            assert slot.start >= datetime(2026, 5, 25, 11, 15, tzinfo=timezone.utc) or \
                   slot.end <= datetime(2026, 5, 25, 9, 45, tzinfo=timezone.utc)

    def test_returns_max_three_suggestions(self):
        client = _make_client()
        session = _make_session()

        time_min = datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc)
        time_max = datetime(2026, 5, 25, 18, 0, tzinfo=timezone.utc)

        with patch.object(client, "list_events", return_value=[]):
            slots = client.find_free_slots(30, time_min, time_max, session, max_suggestions=3)

        assert len(slots) <= 3

    def test_respects_working_hours(self):
        from datetime import time
        client = _make_client()
        session = _make_session()
        session.working_hours_start = time(9, 0)
        session.working_hours_end = time(17, 0)

        time_min = datetime(2026, 5, 25, 6, 0, tzinfo=timezone.utc)
        time_max = datetime(2026, 5, 25, 20, 0, tzinfo=timezone.utc)

        with patch.object(client, "list_events", return_value=[]):
            slots = client.find_free_slots(60, time_min, time_max, session)

        for slot in slots:
            assert slot.start.hour >= 9
            assert slot.end.hour <= 17


# ── _parse_event ──────────────────────────────────────────────────────────────


class TestParseEvent:
    def test_parses_timed_event(self):
        raw = _raw_event()
        event = CalendarClient._parse_event(raw)
        assert event.event_id == "evt1"
        assert event.title == "Team Sync"
        assert event.start.hour == 10
        assert event.end.hour == 11
        assert event.is_recurring is False

    def test_parses_recurring_event(self):
        raw = _raw_event(recurrence="RRULE:FREQ=WEEKLY;BYDAY=MO")
        event = CalendarClient._parse_event(raw)
        assert event.is_recurring is True
        assert event.recurrence == "RRULE:FREQ=WEEKLY;BYDAY=MO"

    def test_parses_all_day_event(self):
        raw = {
            "id": "allday1",
            "summary": "Holiday",
            "start": {"date": "2026-05-25"},
            "end": {"date": "2026-05-26"},
        }
        event = CalendarClient._parse_event(raw)
        assert event.title == "Holiday"
        assert event.start.hour == 0
