# Services — Agentic Calendar Assistant

---

## Service Architecture Overview

The system uses a single-service backend architecture — one AWS Lambda function handles all backend logic. There is no microservices split at the MVP stage. The "services" in this document refer to logical service layers within the Lambda function, not separate deployable units.

```
Frontend (S3)
    |
    | HTTPS POST /chat
    | HTTPS GET  /oauth/callback
    |
API Gateway
    |
Lambda Function
    |
    +-- ChatService          (orchestrates a conversation turn)
    +-- CalendarService      (all calendar operations)
    +-- AuthService          (OAuth lifecycle management)
    +-- PreferenceService    (session preference management)
```

---

## Service 1: ChatService

**Layer**: Agent Orchestrator component

**Purpose**: Orchestrate a complete conversation turn — from receiving the user's message to returning the agent's reply.

**Responsibilities**:
- Accept the user message and current session state
- Invoke Bedrock Client to resolve intent
- Route the resolved intent to the appropriate downstream service (CalendarService, PreferenceService)
- Handle ambiguity by returning a disambiguation prompt without executing any action
- Apply confirmation mode logic before executing write/delete actions
- Update conversation history in session state
- Return the final reply and updated session state

**Orchestration Flow**:
```
User Message
    |
    v
[1] PreferenceService.detect_preference_change()
    |  (update session state if preference command detected)
    v
[2] BedrockClient.invoke()
    |  (resolve intent: action + parameters)
    v
[3] Route by action:
    |-- "read"          --> CalendarService.get_events()
    |-- "create"        --> [confirm?] --> CalendarService.create_event()
    |-- "update"        --> [confirm?] --> CalendarService.reschedule_event()
    |-- "delete"        --> [confirm?] --> CalendarService.delete_event()
    |-- "suggest_slots" --> CalendarService.find_free_slots()
    |-- "clarify"       --> return disambiguation prompt (no action)
    |-- "chat"          --> return conversational reply (no calendar action)
    v
[4] Format and return reply + updated session state
```

**Interactions**:
- Uses: Bedrock Client, CalendarService, PreferenceService
- Called by: API Handler

---

## Service 2: CalendarService

**Layer**: Calendar Client component

**Purpose**: Provide a clean, high-level interface for all Google Calendar operations, abstracting API details and caching.

**Responsibilities**:
- Execute all Google Calendar API v3 operations (list, create, update, delete)
- Manage the session-level in-memory event cache
- Apply exponential backoff on rate limit errors
- Delegate authentication to AuthService
- Return clean, typed `CalendarEvent` objects (not raw API responses)

**Operations**:

| Method | Description | Cache Behaviour |
|--------|-------------|-----------------|
| `get_events(time_min, time_max)` | Fetch events in a time range | Read from cache if available; populate cache on miss |
| `create_event(input)` | Create a new event (single or recurring) | Invalidate cache |
| `reschedule_event(event_id, updates)` | Update event time | Invalidate cache |
| `delete_event(event_id)` | Delete an event | Invalidate cache |
| `find_free_slots(duration, window, prefs)` | Find available slots respecting preferences | Uses cached events if available |

**Interactions**:
- Uses: AuthService (for valid access tokens), Google Calendar API v3
- Called by: ChatService

---

## Service 3: AuthService

**Purpose**: Manage the complete Google OAuth 2.0 lifecycle — authorization, token storage, refresh, and re-auth detection.

**Responsibilities**:
- Handle the OAuth authorization code exchange (called once on first login)
- Store tokens securely in AWS SSM Parameter Store or Secrets Manager
- Provide a valid access token to CalendarService on every API call
- Automatically refresh expired access tokens using the stored refresh token
- Detect and signal invalid/revoked refresh tokens requiring user re-authentication

**Token Lifecycle**:
```
First Login:
  Frontend --> Google OAuth --> redirect with code
  API Handler --> AuthService.exchange_code_for_tokens(code)
  AuthService --> store tokens in SSM/Secrets Manager

Subsequent Calls:
  CalendarService --> AuthService.get_valid_access_token()
  AuthService --> check expiry
    |-- not expired --> return access token
    |-- expired     --> AuthService.refresh_access_token()
                        --> update stored tokens
                        --> return new access token
    |-- refresh invalid --> raise ReAuthRequiredException
                            --> ChatService returns re-auth prompt to user
```

**Interactions**:
- Uses: Google OAuth 2.0 endpoints, AWS SSM Parameter Store / Secrets Manager
- Called by: CalendarService, API Handler (OAuth callback)

---

## Service 4: PreferenceService

**Purpose**: Detect and apply user preference changes expressed in natural language within the chat.

**Responsibilities**:
- Detect preference-setting commands in user messages (working hours, confirmation mode, buffer time)
- Update the session state with new preference values
- Provide the current preferences to the Bedrock Client for system prompt construction

**Detectable Preferences**:

| Preference | Example Commands | Default |
|------------|-----------------|---------|
| Working hours | "My working hours are 8am to 5pm", "I work 9 to 6" | 9:00–18:00 Mon–Fri |
| Confirmation mode | "Stop asking me to confirm", "Always ask before making changes" | On |
| Buffer time | "Add 15 minutes between meetings", "No buffer needed" | 15 minutes |

**Interactions**:
- Uses: No external dependencies (pure session state manipulation)
- Called by: ChatService (before Bedrock invocation on every turn)

---

## Service Interaction Summary

```
API Handler
    |
    +--[chat]--> ChatService
    |                |
    |                +--[intent]--> BedrockClient
    |                |
    |                +--[calendar ops]--> CalendarService
    |                |                       |
    |                |                       +--[auth]--> AuthService
    |                |                                       |
    |                |                                       +--> AWS SSM
    |                |                                       +--> Google OAuth
    |                |
    |                +--[calendar ops]--> Google Calendar API v3
    |
    +--[oauth callback]--> AuthService
```
