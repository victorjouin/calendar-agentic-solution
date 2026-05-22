# Application Design — Agentic Calendar Assistant

---

## 1. Design Overview

Calendar-Agent is a single-user agentic assistant that manages Google Calendar through a conversational web chat interface. The system is built on a serverless AWS architecture using a single Lambda function for all backend logic, Amazon Bedrock for natural language understanding, and the Google Calendar API v3 for calendar operations.

**Architecture Style**: Serverless monolith (single Lambda) with clean internal module separation

**Deployment**:
- Frontend: AWS S3 static website hosting (Plain HTML/CSS/JS)
- Backend: AWS Lambda + API Gateway (Python)
- LLM: Amazon Bedrock (Nova Lite, configurable)
- Auth storage: AWS SSM Parameter Store / Secrets Manager
- Calendar: Google Calendar API v3

---

## 2. System Architecture Diagram

```
+------------------------------------------+
|           USER BROWSER                   |
|                                          |
|  +------------------------------------+  |
|  |        Web Chat UI                 |  |
|  |   (Plain HTML / CSS / JS)          |  |
|  |   Hosted on AWS S3                 |  |
|  +------------------------------------+  |
+------------------------------------------+
                    |
                    | HTTPS REST (JSON)
                    v
+------------------------------------------+
|         AWS API GATEWAY                  |
|   POST /chat                             |
|   GET  /oauth/callback                   |
+------------------------------------------+
                    |
                    | Lambda trigger
                    v
+------------------------------------------+
|         AWS LAMBDA (Python)              |
|                                          |
|  +----------------------------------+    |
|  |       API Handler                |    |
|  |  (routing + serialization)       |    |
|  +----------------------------------+    |
|                  |                       |
|  +----------------------------------+    |
|  |    Agent Orchestrator            |    |
|  |  (conversation + intent routing) |    |
|  +----------------------------------+    |
|         |                  |            |
|  +-------------+  +------------------+  |
|  | Bedrock     |  | Calendar Client  |  |
|  | Client      |  |  + event cache   |  |
|  +-------------+  +------------------+  |
|         |                  |            |
|         |          +------------------+ |
|         |          |   Auth Manager   | |
|         |          +------------------+ |
+---------|----------|-------------------++
          |          |         |
          v          v         v
    +----------+ +--------+ +--------+
    | Amazon   | | Google | | AWS    |
    | Bedrock  | | Cal    | | SSM /  |
    |          | | API v3 | | Secrets|
    +----------+ +--------+ +--------+
                      |
                 +--------+
                 | Google |
                 | OAuth  |
                 +--------+
```

---

## 3. Components

See full detail: `components.md`

| # | Component | Type | Technology | Responsibility |
|---|-----------|------|------------|----------------|
| 1 | Web Chat UI | Frontend | HTML/CSS/JS on S3 | Chat interface, OAuth login initiation |
| 2 | API Handler | Backend | Python Lambda | HTTP routing, request/response serialization |
| 3 | Agent Orchestrator | Backend | Python Lambda | Conversation management, intent routing, session state |
| 4 | Bedrock Client | Backend | Python Lambda + boto3 | NLU via Amazon Bedrock, intent parsing |
| 5 | Calendar Client | Backend | Python Lambda | Google Calendar API operations, event cache |
| 6 | Auth Manager | Backend | Python Lambda + boto3 | OAuth token lifecycle, SSM/Secrets Manager |

---

## 4. Services

See full detail: `services.md`

| Service | Layer | Purpose |
|---------|-------|---------|
| ChatService | Agent Orchestrator | Orchestrate a full conversation turn end-to-end |
| CalendarService | Calendar Client | High-level calendar operations with caching |
| AuthService | Auth Manager | OAuth lifecycle: exchange, store, refresh, re-auth |
| PreferenceService | Agent Orchestrator | Detect and apply user preference changes from chat |

### Core Conversation Flow

```
User Message
    → PreferenceService (detect preference changes)
    → BedrockClient (resolve intent: action + parameters)
    → Route by action:
        read          → CalendarService.get_events()
        create        → [confirm?] → CalendarService.create_event()
        update        → [confirm?] → CalendarService.reschedule_event()
        delete        → [confirm?] → CalendarService.delete_event()
        suggest_slots → CalendarService.find_free_slots()
        clarify       → return disambiguation prompt (no action)
        chat          → return conversational reply (no action)
    → Format reply + update session state
    → Return to API Handler
```

---

## 5. Key Method Signatures

See full detail: `component-methods.md`

**Agent Orchestrator**
```python
process_message(message: str, session_state: SessionState) -> tuple[str, SessionState]
resolve_ambiguity(matches: list[CalendarEvent], action: str) -> str
apply_confirmation(action: CalendarAction, session_state: SessionState) -> str
update_session_preferences(message: str, session_state: SessionState) -> SessionState
```

**Bedrock Client**
```python
invoke(conversation_history: list[dict], user_message: str, system_prompt: str) -> BedrockResponse
build_system_prompt(session_state: SessionState) -> str
```

**Calendar Client**
```python
list_events(time_min: datetime, time_max: datetime, session_state: SessionState) -> list[CalendarEvent]
create_event(event: CalendarEventInput) -> CalendarEvent
update_event(event_id: str, updates: CalendarEventInput) -> CalendarEvent
delete_event(event_id: str) -> bool
find_free_slots(duration_minutes: int, time_min: datetime, time_max: datetime, session_state: SessionState) -> list[TimeSlot]
```

**Auth Manager**
```python
exchange_code_for_tokens(auth_code: str) -> OAuthTokens
get_valid_access_token() -> str
refresh_access_token(refresh_token: str) -> OAuthTokens
store_tokens(tokens: OAuthTokens) -> None
```

---

## 6. Session State Model

The session state is the central data structure passed through every component. It is owned by the Agent Orchestrator and returned to the frontend on every response turn.

```python
@dataclass
class SessionState:
    session_id: str
    conversation_history: list[dict]   # {"role": "user"|"assistant", "content": str}
    working_hours_start: time          # default 09:00
    working_hours_end: time            # default 18:00
    working_days: list[int]            # default [0,1,2,3,4] (Mon–Fri)
    buffer_minutes: int                # default 15
    confirmation_mode: bool            # default True
    event_cache: list[CalendarEvent]   # cleared on every write operation
```

**Session state lifecycle**:
- Created fresh on every new session (no cross-session persistence)
- Passed from frontend to backend on every chat message (as JSON in request body)
- Updated by the backend and returned to frontend on every response
- Frontend stores it in memory (JavaScript variable) for the duration of the session

---

## 7. Component Dependencies

See full detail: `component-dependency.md`

```
Web Chat UI
    → API Handler (HTTPS REST)
        → Agent Orchestrator (function call)
            → Bedrock Client (function call) → Amazon Bedrock (boto3)
            → Calendar Client (function call) → Google Calendar API v3 (HTTPS)
                → Auth Manager (function call) → AWS SSM/Secrets Manager (boto3)
                                               → Google OAuth 2.0 (HTTPS)
```

---

## 8. Project File Structure

```
calendar-agent/                         # Workspace root — application code here
│
├── frontend/
│   ├── index.html                      # Chat UI entry point
│   ├── style.css                       # Chat UI styles
│   └── app.js                          # Chat UI logic (fetch, render, session state)
│
├── backend/
│   ├── lambda_handler.py               # API Handler — Lambda entry point
│   ├── orchestrator.py                 # Agent Orchestrator + PreferenceService
│   ├── bedrock_client.py               # Bedrock Client
│   ├── calendar_client.py              # Calendar Client + CalendarService
│   ├── auth_manager.py                 # Auth Manager + AuthService
│   ├── models.py                       # Shared data models (dataclasses)
│   └── config.py                       # Environment variable loading
│
├── infrastructure/
│   ├── template.yaml                   # AWS SAM / CloudFormation template
│   └── deploy.sh                       # Deployment script
│
├── tests/
│   ├── test_orchestrator.py
│   ├── test_bedrock_client.py
│   ├── test_calendar_client.py
│   └── test_auth_manager.py
│
└── requirements.txt                    # Python dependencies
```

---

## 9. Design Decisions and Rationale

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single Lambda vs microservices | Single Lambda | MVP simplicity; free tier; no inter-service latency |
| Session state location | Frontend (JS memory) + passed on each request | No server-side session store needed; stateless Lambda |
| Event cache scope | In-memory within session state | Reduces Google API calls; no persistence risk |
| Token storage | AWS SSM Parameter Store | Free tier; encrypted; no database needed |
| Frontend framework | Plain HTML/CSS/JS | Minimal dependencies; easy S3 deployment; no build step |
| Backend language | Python | Best AWS Lambda ecosystem; Google API client available |
| Bedrock model | Amazon Nova Lite (default) | Best free-tier balance of speed and capability; swappable |
| Confirmation mode | User-configurable, default on | Balances safety with UX flexibility |
| Working hours | User-configurable via chat, default 9–18 Mon–Fri | Natural language configuration; no settings UI needed |
