"""
lambda_handler.py — AWS Lambda entry point and API Handler.

Routes incoming API Gateway events to the appropriate handler:
  POST /chat              → handle_chat()
  GET  /oauth/callback    → handle_oauth_callback()
  GET  /health            → handle_health_check()

All responses follow the API Gateway proxy integration format.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, time
from typing import Any

from backend.auth_manager import AuthManager, ReAuthRequiredException
from backend.models import SessionState
from backend.orchestrator import Orchestrator, create_new_session

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

# Module-level singletons (reused across warm Lambda invocations)
_orchestrator: Orchestrator | None = None
_auth_manager: AuthManager | None = None


def _get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def _get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


# ── Lambda Handler ────────────────────────────────────────────────────────────


def handler(event: dict, context: Any) -> dict:
    """
    Main Lambda entry point. Routes to the appropriate handler based on
    HTTP method and path.
    """
    method = event.get("httpMethod", "GET").upper()
    path = event.get("path", "/")

    logger.info("Received %s %s", method, path)

    try:
        if method == "POST" and path == "/chat":
            return handle_chat(event)
        if method == "GET" and path.startswith("/oauth/callback"):
            return handle_oauth_callback(event)
        if method == "GET" and path == "/health":
            return handle_health_check()
        if method == "OPTIONS":
            return _cors_response(200, {})

        return _error_response(404, "Not found")

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in Lambda handler: %s", exc)
        return _error_response(
            500,
            "An unexpected error occurred. Please try again.",
        )


# ── Route Handlers ────────────────────────────────────────────────────────────


def handle_chat(event: dict) -> dict:
    """
    Handle a chat message from the frontend.

    Expected request body:
    {
        "message": "<user message>",
        "session_state": { ... }  // optional; omit for new sessions
    }

    Response body:
    {
        "reply": "<agent reply>",
        "session_state": { ... }
    }
    """
    body = _parse_body(event)
    if body is None:
        return _error_response(400, "Invalid JSON in request body")

    message: str = body.get("message", "").strip()
    if not message:
        return _error_response(400, "Missing 'message' field in request body")

    # Deserialise or create session state
    raw_state = body.get("session_state")
    if raw_state:
        try:
            session_state = _deserialise_session_state(raw_state)
        except Exception as exc:
            logger.warning("Failed to deserialise session state: %s — starting fresh", exc)
            session_state = create_new_session()
    else:
        session_state = create_new_session()

    # Check authentication
    auth = _get_auth_manager()
    if not auth.is_authenticated():
        return _success_response(
            200,
            {
                "reply": (
                    "It looks like you haven't connected your Google Calendar yet. "
                    "Please sign in with Google to get started."
                ),
                "session_state": _serialise_session_state(session_state),
                "requires_auth": True,
            },
        )

    # Process the message
    orchestrator = _get_orchestrator()
    try:
        reply, updated_state = orchestrator.process_message(message, session_state)
    except ReAuthRequiredException:
        return _success_response(
            200,
            {
                "reply": (
                    "Your Google Calendar session has expired. "
                    "Please sign in again to continue."
                ),
                "session_state": _serialise_session_state(session_state),
                "requires_auth": True,
            },
        )

    return _success_response(
        200,
        {
            "reply": reply,
            "session_state": _serialise_session_state(updated_state),
        },
    )


def handle_oauth_callback(event: dict) -> dict:
    """
    Handle the Google OAuth 2.0 redirect callback.

    Expected query parameters:
        code  — authorization code from Google
        state — CSRF state token (validated client-side for MVP)

    On success, redirects the browser to the frontend root with ?auth=success.
    """
    params = event.get("queryStringParameters") or {}
    auth_code = params.get("code", "").strip()

    if not auth_code:
        return _error_response(400, "Missing 'code' query parameter")

    auth = _get_auth_manager()
    try:
        auth.exchange_code_for_tokens(auth_code)
        logger.info("OAuth authentication successful")
    except ValueError as exc:
        logger.error("OAuth token exchange failed: %s", exc)
        return _error_response(400, f"Authentication failed: {exc}")

    # Redirect to frontend with success indicator
    frontend_url = os.environ.get("FRONTEND_URL", "/")
    return {
        "statusCode": 302,
        "headers": {
            "Location": f"{frontend_url}?auth=success",
            **_cors_headers(),
        },
        "body": "",
    }


def handle_health_check() -> dict:
    """Return a simple health status."""
    return _success_response(200, {"status": "ok"})


# ── Serialisation Helpers ─────────────────────────────────────────────────────


def _serialise_session_state(state: SessionState) -> dict:
    """
    Convert a SessionState to a JSON-serialisable dict.
    Handles datetime and time objects that are not natively JSON-serialisable.
    """
    d = asdict(state)

    # Convert time objects to "HH:MM" strings
    d["working_hours_start"] = state.working_hours_start.strftime("%H:%M")
    d["working_hours_end"] = state.working_hours_end.strftime("%H:%M")

    # Convert CalendarEvent datetimes to ISO strings
    serialised_cache = []
    for event in state.event_cache:
        e = asdict(event)
        e["start"] = event.start.isoformat()
        e["end"] = event.end.isoformat()
        serialised_cache.append(e)
    d["event_cache"] = serialised_cache

    return d


def _deserialise_session_state(raw: dict) -> SessionState:
    """
    Reconstruct a SessionState from a JSON dict received from the frontend.
    """
    from backend.models import CalendarEvent

    def _parse_time(s: str) -> time:
        h, m = s.split(":")
        return time(int(h), int(m))

    def _parse_event(e: dict) -> CalendarEvent:
        return CalendarEvent(
            event_id=e["event_id"],
            title=e["title"],
            start=datetime.fromisoformat(e["start"]),
            end=datetime.fromisoformat(e["end"]),
            location=e.get("location"),
            recurrence=e.get("recurrence"),
            is_recurring=e.get("is_recurring", False),
        )

    return SessionState(
        session_id=raw.get("session_id", ""),
        conversation_history=raw.get("conversation_history", []),
        working_hours_start=_parse_time(raw.get("working_hours_start", "09:00")),
        working_hours_end=_parse_time(raw.get("working_hours_end", "18:00")),
        working_days=raw.get("working_days", [0, 1, 2, 3, 4]),
        buffer_minutes=raw.get("buffer_minutes", 15),
        confirmation_mode=raw.get("confirmation_mode", True),
        event_cache=[_parse_event(e) for e in raw.get("event_cache", [])],
        pending_action=raw.get("pending_action"),
    )


# ── Response Helpers ──────────────────────────────────────────────────────────


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def _success_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", **_cors_headers()},
        "body": json.dumps(body),
    }


def _error_response(status_code: int, message: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", **_cors_headers()},
        "body": json.dumps({"error": message}),
    }


def _cors_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(body),
    }


def _parse_body(event: dict) -> dict | None:
    """Parse the request body as JSON. Returns None on failure."""
    raw = event.get("body", "{}")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
