"""
test_bedrock_client.py — Unit tests for BedrockClient.

boto3 Bedrock calls are mocked throughout.
"""

from __future__ import annotations

import json
from datetime import time
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.bedrock_client import BedrockClient
from backend.models import BedrockResponse, SessionState


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_session() -> SessionState:
    return SessionState(
        session_id="test",
        working_hours_start=time(9, 0),
        working_hours_end=time(18, 0),
        working_days=[0, 1, 2, 3, 4],
        buffer_minutes=15,
        confirmation_mode=True,
    )


def _bedrock_response(action: str, params: dict, reply: str) -> dict:
    """Build a mock Bedrock Converse API response."""
    content = json.dumps(
        {"action": action, "parameters": params, "reply": reply, "needs_clarification": False}
    )
    return {
        "output": {
            "message": {
                "content": [{"text": content}]
            }
        }
    }


# ── build_system_prompt ───────────────────────────────────────────────────────


class TestBuildSystemPrompt:
    def test_includes_working_hours(self):
        client = BedrockClient.__new__(BedrockClient)
        session = _make_session()
        prompt = client.build_system_prompt(session)
        assert "09:00" in prompt
        assert "18:00" in prompt

    def test_includes_buffer_minutes(self):
        client = BedrockClient.__new__(BedrockClient)
        session = _make_session()
        session.buffer_minutes = 30
        prompt = client.build_system_prompt(session)
        assert "30" in prompt

    def test_confirmation_mode_on(self):
        client = BedrockClient.__new__(BedrockClient)
        session = _make_session()
        session.confirmation_mode = True
        prompt = client.build_system_prompt(session)
        assert "ON" in prompt

    def test_confirmation_mode_off(self):
        client = BedrockClient.__new__(BedrockClient)
        session = _make_session()
        session.confirmation_mode = False
        prompt = client.build_system_prompt(session)
        assert "OFF" in prompt


# ── parse_response ────────────────────────────────────────────────────────────


class TestParseResponse:
    def test_parses_valid_json(self):
        client = BedrockClient.__new__(BedrockClient)
        raw = json.dumps(
            {
                "action": "read",
                "parameters": {"time_range": "today"},
                "reply": "Here are your events.",
                "needs_clarification": False,
            }
        )
        result = client.parse_response(raw, "What do I have today?")
        assert result.action == "read"
        assert result.parameters["time_range"] == "today"
        assert result.needs_clarification is False

    def test_parses_json_in_markdown_code_block(self):
        client = BedrockClient.__new__(BedrockClient)
        raw = '```json\n{"action": "chat", "parameters": {}, "reply": "Hello!", "needs_clarification": false}\n```'
        result = client.parse_response(raw, "Hi")
        assert result.action == "chat"
        assert result.reply == "Hello!"

    def test_falls_back_to_chat_on_invalid_json(self):
        client = BedrockClient.__new__(BedrockClient)
        result = client.parse_response("This is not JSON at all.", "Hello")
        assert result.action == "chat"
        assert result.reply == "This is not JSON at all."

    def test_unknown_action_defaults_to_chat(self):
        client = BedrockClient.__new__(BedrockClient)
        raw = json.dumps(
            {"action": "unknown_action", "parameters": {}, "reply": "test", "needs_clarification": False}
        )
        result = client.parse_response(raw, "test")
        assert result.action == "chat"

    def test_needs_clarification_true(self):
        client = BedrockClient.__new__(BedrockClient)
        raw = json.dumps(
            {
                "action": "clarify",
                "parameters": {"question": "Which meeting?"},
                "reply": "Which meeting did you mean?",
                "needs_clarification": True,
            }
        )
        result = client.parse_response(raw, "cancel my meeting")
        assert result.needs_clarification is True
        assert result.action == "clarify"


# ── invoke ────────────────────────────────────────────────────────────────────


class TestInvoke:
    def test_successful_invocation(self):
        session = _make_session()
        client = BedrockClient()

        mock_boto = MagicMock()
        mock_boto.converse.return_value = _bedrock_response(
            "read", {"time_range": "today"}, "Here are your events for today."
        )

        with patch.object(client, "_client", mock_boto):
            result = client.invoke([], "What do I have today?", session)

        assert result.action == "read"
        assert result.parameters["time_range"] == "today"

    def test_raises_runtime_error_on_client_error(self):
        session = _make_session()
        client = BedrockClient()

        error_response = {"Error": {"Code": "ServiceUnavailableException", "Message": "down"}}
        mock_boto = MagicMock()
        mock_boto.converse.side_effect = ClientError(error_response, "Converse")

        with patch.object(client, "_client", mock_boto):
            with pytest.raises(RuntimeError, match="AI service"):
                client.invoke([], "Hello", session)

    def test_passes_conversation_history(self):
        session = _make_session()
        client = BedrockClient()

        history = [
            {"role": "user", "content": "What do I have today?"},
            {"role": "assistant", "content": "You have 3 meetings."},
        ]

        mock_boto = MagicMock()
        mock_boto.converse.return_value = _bedrock_response("chat", {}, "Sure!")

        with patch.object(client, "_client", mock_boto):
            client.invoke(history, "Thanks", session)

        call_kwargs = mock_boto.converse.call_args[1]
        messages = call_kwargs["messages"]
        # History (2) + new user message (1) = 3 messages
        assert len(messages) == 3
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"][0]["text"] == "Thanks"
