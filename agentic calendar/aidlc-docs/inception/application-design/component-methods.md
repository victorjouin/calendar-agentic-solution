# Component Methods — Agentic Calendar Assistant

> **Note**: This document defines method signatures and high-level purposes.
> Detailed business logic and algorithms are defined in Functional Design (CONSTRUCTION phase).

---

## Component 2: API Handler

### `handle_chat(event: dict) -> dict`
- **Purpose**: Process an incoming chat message from the frontend
- **Input**: API Gateway event containing `{ session_id: str, message: str, session_state: dict }`
- **Output**: `{ status: int, body: { reply: str, session_state: dict } }`
- **Notes**: Entry point for all conversational interactions

### `handle_oauth_callback(event: dict) -> dict`
- **Purpose**: Handle the Google OAuth 2.0 redirect callback and exchange the authorization code for tokens
- **Input**: API Gateway event containing `{ code: str, state: str }`
- **Output**: `{ status: int, body: { authenticated: bool } }`
- **Notes**: Delegates token exchange and storage to Auth Manager

### `handle_health_check(event: dict) -> dict`
- **Purpose**: Return a simple health status for monitoring
- **Input**: API Gateway event
- **Output**: `{ status: 200, body: { status: "ok" } }`

---

## Component 3: Agent Orchestrator

### `process_message(message: str, session_state: SessionState) -> tuple[str, SessionState]`
- **Purpose**: Main orchestration method — interprets user intent, dispatches action, returns response
- **Input**: User message string, current session state (conversation history, preferences, cache)
- **Output**: Tuple of (agent reply string, updated session state)
- **Notes**: Calls Bedrock Client for intent resolution, then Calendar Client for execution

### `resolve_ambiguity(matches: list[CalendarEvent], action: str) -> str`
- **Purpose**: Format a disambiguation prompt when multiple events match a user request
- **Input**: List of matching events, the requested action (delete/reschedule)
- **Output**: Formatted string presenting options to the user
- **Notes**: Does not execute any action — returns prompt only

### `apply_confirmation(action: CalendarAction, session_state: SessionState) -> str`
- **Purpose**: Apply the user's confirmation preference before executing a write/delete action
- **Input**: Resolved calendar action, current session state (confirmation mode flag)
- **Output**: Confirmation prompt string (if confirmation on) or empty string (if confirmation off)
- **Notes**: Returns empty string when confirmation mode is off, signalling immediate execution

### `update_session_preferences(message: str, session_state: SessionState) -> SessionState`
- **Purpose**: Detect and apply user preference changes expressed in natural language
- **Input**: User message, current session state
- **Output**: Updated session state with new preferences (working hours, confirmation mode, buffer time)
- **Notes**: Handles commands like "My working hours are 8am to 5pm"

### `invalidate_event_cache(session_state: SessionState) -> SessionState`
- **Purpose**: Clear the in-memory event cache after a write operation
- **Input**: Current session state
- **Output**: Updated session state with empty event cache

---

## Component 4: Bedrock Client

### `invoke(conversation_history: list[dict], user_message: str, system_prompt: str) -> BedrockResponse`
- **Purpose**: Send a conversation turn to Amazon Bedrock and return the parsed response
- **Input**: Full conversation history, current user message, system prompt with agent instructions
- **Output**: `BedrockResponse` containing `{ action: str, parameters: dict, reply: str, needs_clarification: bool }`
- **Notes**: Uses the Bedrock Converse API; model ID loaded from environment variable

### `build_system_prompt(session_state: SessionState) -> str`
- **Purpose**: Construct the system prompt injected into every Bedrock call, including current session preferences
- **Input**: Current session state (working hours, confirmation mode, buffer time)
- **Output**: Formatted system prompt string
- **Notes**: Preferences are injected so the model is always aware of current user settings

### `parse_response(raw_response: dict) -> BedrockResponse`
- **Purpose**: Extract structured intent and parameters from the raw Bedrock API response
- **Input**: Raw Bedrock API response dict
- **Output**: Structured `BedrockResponse` object
- **Notes**: Handles cases where the model returns clarification requests or partial information

---

## Component 5: Calendar Client

### `list_events(time_min: datetime, time_max: datetime, session_state: SessionState) -> list[CalendarEvent]`
- **Purpose**: Retrieve calendar events within a time range, using session cache when available
- **Input**: Start datetime, end datetime, current session state (for cache lookup)
- **Output**: List of `CalendarEvent` objects
- **Notes**: Returns cached results if available; fetches from Google API otherwise

### `create_event(event: CalendarEventInput) -> CalendarEvent`
- **Purpose**: Create a new calendar event (single or recurring) via the Google Calendar API
- **Input**: `CalendarEventInput` containing title, start, end, recurrence rule (optional)
- **Output**: Created `CalendarEvent` with Google-assigned event ID
- **Notes**: Invalidates session event cache after creation

### `update_event(event_id: str, updates: CalendarEventInput) -> CalendarEvent`
- **Purpose**: Update an existing calendar event (used for rescheduling)
- **Input**: Google Calendar event ID, updated fields
- **Output**: Updated `CalendarEvent`
- **Notes**: Invalidates session event cache after update

### `delete_event(event_id: str) -> bool`
- **Purpose**: Delete a calendar event by its Google Calendar event ID
- **Input**: Google Calendar event ID string
- **Output**: Boolean indicating success
- **Notes**: Invalidates session event cache after deletion

### `find_free_slots(duration_minutes: int, time_min: datetime, time_max: datetime, session_state: SessionState) -> list[TimeSlot]`
- **Purpose**: Find available time slots within a window, respecting working hours and buffer rules
- **Input**: Required duration in minutes, search window start/end, session state (working hours, buffer time)
- **Output**: List of up to 3 `TimeSlot` objects with start time and rationale
- **Notes**: Detailed slot selection algorithm defined in Functional Design

---

## Component 6: Auth Manager

### `exchange_code_for_tokens(auth_code: str) -> OAuthTokens`
- **Purpose**: Exchange a Google OAuth authorization code for access and refresh tokens
- **Input**: Authorization code string from OAuth callback
- **Output**: `OAuthTokens` containing access token, refresh token, and expiry
- **Notes**: Calls Google OAuth token endpoint

### `store_tokens(tokens: OAuthTokens) -> None`
- **Purpose**: Persist OAuth tokens securely in AWS SSM Parameter Store or Secrets Manager
- **Input**: `OAuthTokens` object
- **Output**: None
- **Notes**: Tokens stored encrypted; parameter names configurable via environment variables

### `get_valid_access_token() -> str`
- **Purpose**: Retrieve a valid access token, refreshing it automatically if expired
- **Input**: None (reads from SSM/Secrets Manager)
- **Output**: Valid access token string
- **Notes**: Raises `ReAuthRequiredException` if refresh token is invalid or revoked

### `refresh_access_token(refresh_token: str) -> OAuthTokens`
- **Purpose**: Use the stored refresh token to obtain a new access token from Google
- **Input**: Refresh token string
- **Output**: Updated `OAuthTokens` with new access token and expiry
- **Notes**: Updates stored tokens in SSM/Secrets Manager after refresh

---

## Shared Data Models

```python
@dataclass
class CalendarEvent:
    event_id: str
    title: str
    start: datetime
    end: datetime
    location: str | None
    recurrence: str | None  # iCal RRULE string, None for single events
    is_recurring: bool

@dataclass
class CalendarEventInput:
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    recurrence: str | None = None  # iCal RRULE string

@dataclass
class TimeSlot:
    start: datetime
    end: datetime
    rationale: str

@dataclass
class BedrockResponse:
    action: str           # "read", "create", "update", "delete", "suggest_slots", "set_preference", "clarify", "chat"
    parameters: dict
    reply: str
    needs_clarification: bool

@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime

@dataclass
class SessionState:
    session_id: str
    conversation_history: list[dict]   # list of {"role": "user"|"assistant", "content": str}
    working_hours_start: time          # default 09:00
    working_hours_end: time            # default 18:00
    working_days: list[int]            # default [0,1,2,3,4] (Mon–Fri)
    buffer_minutes: int                # default 15
    confirmation_mode: bool            # default True
    event_cache: list[CalendarEvent]   # session-level cache, cleared on write
```
