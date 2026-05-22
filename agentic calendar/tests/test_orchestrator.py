"""
test_orchestrator.py — Unit tests for the Agent Orchestrator.

BedrockClient and CalendarClient are mocked throughout.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.models import (
    BedrockResponse,
    CalendarEvent,
    CalendarEventInput,
    SessionState,
)
from backend.orchestrator import Orchestrator, create_new_session


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session() -> SessionState:
    return SessionState(
        session_id="test-session",
        working_hours_start=time(9, 0),
        working_hours_end=time(18, 0),
        working_days=[0, 1, 2, 3, 4],
        buffer_minutes=15,
        confirmation_mode=True,
    )


def _make_event(
    event_id="evt1",
    title="Team Sync",
    start_hour=10,
    end_hour=11,
) -> CalendarEvent:
    base = datetime(2026, 5, 25, tzinfo=timezone.utc)
    return CalendarEvent(
        event_id=event_id,
        title=title,
        start=base.replace(hour=start_hour),
        end=base.replace(hour=end_hour),
    )


def _make_orchestrator(
    bedrock_response: BedrockResponse | None = None,
) -> tuple[Orchestrator, MagicMock, MagicMock]:
    mock_bedrock = MagicMock()
    mock_calendar = MagicMock()
    mock_auth = MagicMock()
    mock_auth.is_authenticated.return_value = True

    if bedrock_response:
        mock_bedrock.invoke.return_value = bedrock_response

    orch = Orchestrator(
        bedrock_client=mock_bedrock,
        calendar_client=mock_calendar,
        auth_manager=mock_auth,
    )
    return orch, mock_bedrock, mock_calendar


# ── create_new_session ────────────────────────────────────────────────────────


class TestCreateNewSession:
    def test_creates_session_with_defaults(self):
        session = create_new_session()
        assert session.session_id != ""
        assert session.confirmation_mode is True
        assert session.buffer_minutes == 15
        assert session.working_hours_start == time(9, 0)
        assert session.working_hours_end == time(18, 0)
        assert session.event_cache == []
        assert session.conversation_history == []


# ── update_session_preferences ───────────────────────────────────────────────


class TestUpdateSessionPreferences:
    def test_updates_working_hours(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        updated = orch.update_session_preferences(
            "My working hours are 8am to 5pm", session
        )
        assert updated.working_hours_start == time(8, 0)
        assert updated.working_hours_end == time(17, 0)

    def test_disables_confirmation_mode(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        assert session.confirmation_mode is True
        updated = orch.update_session_preferences(
            "Stop asking me to confirm every action", session
        )
        assert updated.confirmation_mode is False

    def test_enables_confirmation_mode(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        session.confirmation_mode = False
        updated = orch.update_session_preferences(
            "Always ask before making changes", session
        )
        assert updated.confirmation_mode is True

    def test_updates_buffer_minutes(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        updated = orch.update_session_preferences(
            "Add 30 minute buffer between meetings", session
        )
        assert updated.buffer_minutes == 30

    def test_no_change_on_unrelated_message(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        updated = orch.update_session_preferences("What do I have today?", session)
        assert updated.working_hours_start == time(9, 0)
        assert updated.confirmation_mode is True
        assert updated.buffer_minutes == 15


# ── resolve_ambiguity ─────────────────────────────────────────────────────────


class TestResolveAmbiguity:
    def test_formats_numbered_list(self):
        orch, _, _ = _make_orchestrator()
        events = [
            _make_event("e1", "Team Sync", 10, 11),
            _make_event("e2", "1:1 with Manager", 14, 15),
        ]
        result = orch.resolve_ambiguity(events, "cancel")
        assert "1." in result
        assert "2." in result
        assert "Team Sync" in result
        assert "1:1 with Manager" in result
        assert "cancel" in result

    def test_includes_event_times(self):
        orch, _, _ = _make_orchestrator()
        events = [_make_event("e1", "Meeting", 10, 11)]
        result = orch.resolve_ambiguity(events, "delete")
        assert "10:00" in result


# ── apply_confirmation ────────────────────────────────────────────────────────


class TestApplyConfirmation:
    def test_returns_prompt_when_confirmation_on(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        session.confirmation_mode = True
        result = orch.apply_confirmation("delete Team Sync", session)
        assert result != ""
        assert "delete Team Sync" in result

    def test_returns_empty_when_confirmation_off(self):
        orch, _, _ = _make_orchestrator()
        session = _make_session()
        session.confirmation_mode = False
        result = orch.apply_confirmation("delete Team Sync", session)
        assert result == ""


# ── process_message — read ────────────────────────────────────────────────────


class TestProcessMessageRead:
    def test_read_returns_event_summary(self):
        bedrock_resp = BedrockResponse(
            action="read",
            parameters={"time_range": "today"},
            reply="",
        )
        orch, _, mock_calendar = _make_orchestrator(bedrock_resp)
        session = _make_session()

        mock_calendar.list_events.return_value = [
            _make_event("e1", "Team Sync", 10, 11)
        ]

        reply, updated = orch.process_message("What do I have today?", session)

        assert "Team Sync" in reply
        assert len(updated.conversation_history) == 2

    def test_read_empty_calendar(self):
        bedrock_resp = BedrockResponse(
            action="read",
            parameters={"time_range": "today"},
            reply="",
        )
        orch, _, mock_calendar = _make_orchestrator(bedrock_resp)
        session = _make_session()
        mock_calendar.list_events.return_value = []

        reply, _ = orch.process_message("What do I have today?", session)

        assert "no events" in reply.lower()


# ── process_message — delete ──────────────────────────────────────────────────


class TestProcessMessageDelete:
    def test_delete_with_confirmation_on_returns_prompt(self):
        bedrock_resp = BedrockResponse(
            action="delete",
            parameters={"event_description": "team sync"},
            reply="",
        )
        orch, _, mock_calendar = _make_orchestrator(bedrock_resp)
        session = _make_session()
        session.confirmation_mode = True

        mock_calendar.list_events.return_value = [
            _make_event("e1", "Team Sync", 10, 11)
        ]

        reply, updated = orch.process_message("Cancel my team sync", session)

        assert "confirm" in reply.lower() or "shall i" in reply.lower()
        assert updated.pending_action is not None
        assert updated.pending_action["type"] == "delete"

    def test_delete_with_confirmation_off_executes_immediately(self):
        bedrock_resp = BedrockResponse(
            action="delete",
            parameters={"event_description": "team sync"},
            reply="",
        )
        orch, _, mock_calendar = _make_orchestrator(bedrock_resp)
        session = _make_session()
        session.confirmation_mode = False

        mock_calendar.list_events.return_value = [
            _make_event("e1", "Team Sync", 10, 11)
        ]
        mock_calendar.delete_event.return_value = True

        reply, updated = orch.process_message("Cancel my team sync", session)

        mock_calendar.delete_event.assert_called_once()
        assert "cancelled" in reply.lower() or "done" in reply.lower()

    def test_delete_ambiguous_presents_options(self):
        bedrock_resp = BedrockResponse(
            action="delete",
            parameters={"event_description": "meeting"},
            reply="",
        )
        orch, _, mock_calendar = _make_orchestrator(bedrock_resp)
        session = _make_session()

        mock_calendar.list_events.return_value = [
            _make_event("e1", "Team Meeting", 10, 11),
            _make_event("e2", "1:1 Meeting", 14, 15),
        ]

        reply, updated = orch.process_message("Cancel my meeting", session)

        assert "1." in reply and "2." in reply
        assert updated.pending_action["type"] == "delete_disambiguate"

    def test_delete_not_found_returns_helpful_message(self):
        bedrock_resp = BedrockResponse(
            action="delete",
            parameters={"event_description": "nonexistent event"},
            reply="",
        )
        orch, _, mock_calendar = _make_orchestrator(bedrock_resp)
        session = _make_session()
        mock_calendar.list_events.return_value = []

        reply, _ = orch.process_message("Cancel my nonexistent event", session)

        assert "couldn't find" in reply.lower()


# ── process_message — pending action resolution ───────────────────────────────


class TestPendingActionResolution:
    def test_yes_confirms_delete(self):
        orch, _, mock_calendar = _make_orchestrator()
        session = _make_session()
        session.pending_action = {
            "type": "delete",
            "event_id": "evt1",
            "title": "Team Sync",
        }
        mock_calendar.delete_event.return_value = True

        reply, updated = orch.process_message("yes", session)

        mock_calendar.delete_event.assert_called_once_with("evt1", updated)
        assert updated.pending_action is None
        assert "cancelled" in reply.lower() or "done" in reply.lower()

    def test_no_cancels_pending_action(self):
        orch, _, mock_calendar = _make_orchestrator()
        session = _make_session()
        session.pending_action = {
            "type": "delete",
            "event_id": "evt1",
            "title": "Team Sync",
        }

        reply, updated = orch.process_message("no", session)

        mock_calendar.delete_event.assert_not_called()
        assert updated.pending_action is None
        assert "cancelled" in reply.lower() or "no problem" in reply.lower()

    def test_slot_selection_creates_event(self):
        orch, _, mock_calendar = _make_orchestrator()
        session = _make_session()
        session.confirmation_mode = False
        session.pending_action = {
            "type": "pick_slot",
            "title": "Deep Work",
            "duration_minutes": 120,
            "recurrence": None,
            "slots": [
                {
                    "start": "2026-05-25T14:00:00+00:00",
                    "end": "2026-05-25T16:00:00+00:00",
                }
            ],
        }

        created_event = _make_event("new-evt", "Deep Work", 14, 16)
        mock_calendar.create_event.return_value = created_event

        reply, updated = orch.process_message("1", session)

        mock_calendar.create_event.assert_called_once()
        assert updated.pending_action is None
        assert "Deep Work" in reply


# ── process_message — chat ────────────────────────────────────────────────────


class TestProcessMessageChat:
    def test_chat_returns_model_reply(self):
        bedrock_resp = BedrockResponse(
            action="chat",
            parameters={},
            reply="I can help you manage your calendar!",
        )
        orch, _, _ = _make_orchestrator(bedrock_resp)
        session = _make_session()

        reply, updated = orch.process_message("What can you do?", session)

        assert reply == "I can help you manage your calendar!"
        assert len(updated.conversation_history) == 2


# ── process_message — bedrock error ──────────────────────────────────────────


class TestProcessMessageBedrockError:
    def test_bedrock_error_returns_friendly_message(self):
        orch, mock_bedrock, _ = _make_orchestrator()
        session = _make_session()
        mock_bedrock.invoke.side_effect = RuntimeError(
            "I'm having trouble connecting to my AI service right now."
        )

        reply, _ = orch.process_message("Hello", session)

        assert "trouble" in reply.lower() or "service" in reply.lower()


# ── conversation history ──────────────────────────────────────────────────────


class TestConversationHistory:
    def test_history_grows_with_each_turn(self):
        bedrock_resp = BedrockResponse(action="chat", parameters={}, reply="Hi!")
        orch, mock_bedrock, _ = _make_orchestrator(bedrock_resp)
        session = _make_session()

        _, session = orch.process_message("Hello", session)
        assert len(session.conversation_history) == 2

        mock_bedrock.invoke.return_value = BedrockResponse(
            action="chat", parameters={}, reply="Sure!"
        )
        _, session = orch.process_message("Thanks", session)
        assert len(session.conversation_history) == 4
