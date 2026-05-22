"""
bedrock_client.py — Amazon Bedrock integration for natural language understanding.

Responsibilities:
- Construct system prompts that include current session preferences
- Invoke the Amazon Bedrock Converse API with conversation history
- Parse the model response into a structured BedrockResponse
- Handle Bedrock API errors and surface them clearly
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend import config
from backend.models import BedrockResponse, SessionState, VALID_ACTIONS

logger = logging.getLogger(__name__)

# ── System Prompt Template ────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """You are Calendar-Agent, an AI assistant that manages a user's Google Calendar.

Your job is to understand the user's intent and return a structured JSON response.

## Current Session Preferences
- Working hours: {working_hours_start} to {working_hours_end}, {working_days}
- Buffer between meetings: {buffer_minutes} minutes
- Confirmation mode: {confirmation_mode}

## Response Format
You MUST always respond with a valid JSON object in this exact format:
{{
  "action": "<one of: read, create, update, delete, suggest_slots, set_preference, clarify, chat>",
  "parameters": {{<action-specific parameters>}},
  "reply": "<natural language reply to show the user>",
  "needs_clarification": <true|false>
}}

## Action Parameters

**read**: Fetch calendar events
  - "time_range": "today" | "this_week" | "tomorrow" | "next_week" | "<ISO date range>"

**create**: Create a new event
  - "title": string
  - "duration_minutes": integer
  - "preferred_window": string (e.g. "tomorrow afternoon", "Friday morning")
  - "exact_start": ISO datetime string (if user specified exact time)
  - "recurrence": iCal RRULE string (e.g. "RRULE:FREQ=WEEKLY;BYDAY=FR") or null

**update**: Reschedule an existing event
  - "event_description": string (how the user described the event)
  - "new_time": string (when to move it to)

**delete**: Delete an event
  - "event_description": string (how the user described the event)

**suggest_slots**: Find free time slots
  - "duration_minutes": integer
  - "preferred_window": string

**set_preference**: Update a session preference
  - "preference": "working_hours" | "confirmation_mode" | "buffer_minutes"
  - "value": the new value (string for working_hours, boolean for confirmation_mode, integer for buffer_minutes)

**clarify**: Need more information
  - "question": string (what you need to know)

**chat**: General conversation, no calendar action needed
  (no specific parameters required)

## Rules
- NEVER take a write or delete action without the user's confirmation (unless confirmation_mode is false)
- When a request is ambiguous (could match multiple events), set action to "clarify"
- Always be helpful, concise, and friendly in the "reply" field
- The "reply" field is what the user sees — make it natural and clear
- For date/time parsing, assume the user's local timezone unless specified
"""


class BedrockClient:
    """Amazon Bedrock client for natural language understanding."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "bedrock-runtime", region_name=config.BEDROCK_REGION
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def invoke(
        self,
        conversation_history: list[dict],
        user_message: str,
        session_state: SessionState,
    ) -> BedrockResponse:
        """
        Send a conversation turn to Amazon Bedrock and return the parsed response.

        Args:
            conversation_history: Previous turns in the session.
            user_message: The current user message.
            session_state: Current session state (used to build system prompt).

        Returns:
            Parsed BedrockResponse with action, parameters, reply, and clarification flag.

        Raises:
            RuntimeError: If Bedrock is unavailable or returns an unexpected error.
        """
        system_prompt = self.build_system_prompt(session_state)

        # Build messages list for the Converse API
        messages = list(conversation_history)
        messages.append({"role": "user", "content": user_message})

        # Convert to Bedrock Converse API format
        converse_messages = [
            {"role": m["role"], "content": [{"text": m["content"]}]}
            for m in messages
        ]

        try:
            response = self._client.converse(
                modelId=config.BEDROCK_MODEL_ID,
                system=[{"text": system_prompt}],
                messages=converse_messages,
                inferenceConfig={
                    "maxTokens": config.BEDROCK_MAX_TOKENS,
                    "temperature": 0.1,  # Low temperature for consistent structured output
                },
            )
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            logger.error("Bedrock API error: %s — %s", error_code, exc)
            raise RuntimeError(
                f"I'm having trouble connecting to my AI service right now "
                f"(error: {error_code}). Please try again in a moment."
            ) from exc

        raw_text = response["output"]["message"]["content"][0]["text"]
        logger.debug("Bedrock raw response: %s", raw_text[:200])

        return self.parse_response(raw_text, user_message)

    def build_system_prompt(self, session_state: SessionState) -> str:
        """
        Construct the system prompt injected into every Bedrock call.
        Includes current session preferences so the model is always aware of them.

        Args:
            session_state: Current session state.

        Returns:
            Formatted system prompt string.
        """
        working_days_names = [
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][d]
            for d in session_state.working_days
        ]

        return _SYSTEM_PROMPT_TEMPLATE.format(
            working_hours_start=session_state.working_hours_start.strftime("%H:%M"),
            working_hours_end=session_state.working_hours_end.strftime("%H:%M"),
            working_days=", ".join(working_days_names),
            buffer_minutes=session_state.buffer_minutes,
            confirmation_mode="ON (ask before every write/delete)"
            if session_state.confirmation_mode
            else "OFF (execute immediately)",
        )

    def parse_response(self, raw_text: str, original_message: str) -> BedrockResponse:
        """
        Extract structured intent and parameters from the raw Bedrock response text.

        Args:
            raw_text: The raw text returned by the model.
            original_message: The original user message (used for fallback reply).

        Returns:
            Structured BedrockResponse object.
        """
        # Extract JSON from the response (model may wrap it in markdown code blocks)
        json_str = self._extract_json(raw_text)

        try:
            data: dict[str, Any] = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse Bedrock response as JSON: %s", raw_text[:200])
            return BedrockResponse(
                action="chat",
                parameters={},
                reply=raw_text.strip(),
                needs_clarification=False,
            )

        action = data.get("action", "chat")
        if action not in VALID_ACTIONS:
            logger.warning("Unknown action '%s' from Bedrock — defaulting to chat", action)
            action = "chat"

        return BedrockResponse(
            action=action,
            parameters=data.get("parameters", {}),
            reply=data.get("reply", ""),
            needs_clarification=bool(data.get("needs_clarification", False)),
        )

    # ── Private Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> str:
        """
        Extract a JSON object from text that may contain markdown code fences.
        Returns the raw text unchanged if no code fence is found.
        """
        # Handle ```json ... ``` or ``` ... ``` blocks
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    return stripped
        # Try to find a bare JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text
