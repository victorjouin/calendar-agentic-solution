# Code Summary — Unit 1: Backend Core

---

## Generated Files

### Backend Modules (`backend/`)

| File | Purpose | Key Exports |
|------|---------|-------------|
| `backend/__init__.py` | Python package marker | — |
| `backend/config.py` | Environment variable loading and defaults | All config constants |
| `backend/models.py` | Shared dataclasses | `CalendarEvent`, `CalendarEventInput`, `TimeSlot`, `BedrockResponse`, `OAuthTokens`, `SessionState` |
| `backend/auth_manager.py` | Google OAuth 2.0 lifecycle | `AuthManager`, `ReAuthRequiredException` |
| `backend/calendar_client.py` | Google Calendar API v3 integration | `CalendarClient` |
| `backend/bedrock_client.py` | Amazon Bedrock NLU integration | `BedrockClient` |
| `backend/orchestrator.py` | Agent orchestration + PreferenceService | `Orchestrator`, `create_new_session` |
| `backend/lambda_handler.py` | Lambda entry point + API Handler | `handler` (Lambda handler function) |

### Tests (`tests/`)

| File | Tests |
|------|-------|
| `tests/__init__.py` | Python package marker |
| `tests/test_auth_manager.py` | Token exchange, storage, retrieval, refresh, re-auth detection |
| `tests/test_calendar_client.py` | List events (cache + API), create, update, delete, find free slots, event parsing |
| `tests/test_bedrock_client.py` | System prompt construction, response parsing, Bedrock invocation, error handling |
| `tests/test_orchestrator.py` | All intent routes, ambiguity handling, confirmation mode, preference updates, conversation history |

### Infrastructure (`infrastructure/`)

| File | Purpose |
|------|---------|
| `infrastructure/template.yaml` | AWS SAM / CloudFormation template — Lambda, API Gateway, IAM role, SSM parameter |
| `infrastructure/deploy.sh` | Interactive deployment script (SAM build + deploy) |

### Root

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies (pinned versions) |

---

## Module Responsibilities

### `config.py`
Centralises all configuration. Every tunable value is read from an environment variable with a sensible default. No hardcoded values in business logic.

### `models.py`
All inter-module data exchange uses typed Python dataclasses. `SessionState` is the central object — it is serialised to JSON and round-tripped through the frontend on every request, making the Lambda stateless.

### `auth_manager.py`
Owns the complete Google OAuth 2.0 lifecycle:
1. Exchange authorization code → access + refresh tokens
2. Store tokens encrypted in AWS SSM Parameter Store
3. Retrieve tokens; auto-refresh on expiry
4. Raise `ReAuthRequiredException` when refresh token is invalid/revoked

### `calendar_client.py`
Wraps the Google Calendar API v3:
- Session-level in-memory event cache (populated on read, cleared on every write)
- Exponential backoff on HTTP 429 rate limit responses
- `find_free_slots()` respects working hours, buffer time, and existing events
- Returns typed `CalendarEvent` objects (not raw API dicts)

### `bedrock_client.py`
Wraps the Amazon Bedrock Converse API:
- Builds a system prompt that includes current session preferences (working hours, confirmation mode, buffer)
- Instructs the model to return structured JSON with `action`, `parameters`, `reply`, `needs_clarification`
- Parses the response, handles markdown code fences, falls back to `chat` action on parse failure

### `orchestrator.py`
The core agent logic:
- Detects preference changes in user messages before invoking Bedrock
- Routes Bedrock-resolved intents to CalendarClient operations
- Manages pending actions (confirmation prompts, disambiguation, slot selection)
- Maintains conversation history in `SessionState`
- `create_new_session()` factory creates a fresh session with config defaults

### `lambda_handler.py`
The Lambda entry point:
- Routes `POST /chat`, `GET /oauth/callback`, `GET /health`
- Serialises/deserialises `SessionState` to/from JSON (handles `datetime` and `time` objects)
- Returns CORS headers on all responses
- Module-level singletons for `Orchestrator` and `AuthManager` (reused across warm invocations)

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Amazon Bedrock model ID |
| `BEDROCK_REGION` | `us-east-1` | AWS region for Bedrock |
| `BEDROCK_MAX_TOKENS` | `1024` | Max tokens per Bedrock response |
| `GOOGLE_CLIENT_ID` | *(required)* | Google OAuth app client ID |
| `GOOGLE_CLIENT_SECRET` | *(required)* | Google OAuth app client secret |
| `GOOGLE_REDIRECT_URI` | *(required)* | OAuth callback URL |
| `SSM_TOKEN_PATH` | `/calendar-agent/oauth` | SSM path for OAuth token storage |
| `AWS_REGION` | `us-east-1` | AWS region for SSM |
| `FRONTEND_URL` | *(empty)* | Frontend URL for OAuth redirect |
| `DEFAULT_WORKING_HOURS_START_HOUR` | `9` | Default working hours start (hour) |
| `DEFAULT_WORKING_HOURS_END_HOUR` | `18` | Default working hours end (hour) |
| `DEFAULT_BUFFER_MINUTES` | `15` | Default buffer between meetings |
| `DEFAULT_CONFIRMATION_MODE` | `true` | Default confirmation mode |
| `CALENDAR_MAX_RESULTS` | `50` | Max events per Google Calendar API call |
| `CALENDAR_MAX_RETRIES` | `3` | Max retries on rate limit |
| `CALENDAR_BACKOFF_BASE_SECONDS` | `1.0` | Base backoff delay (doubles each retry) |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Send a user message; returns agent reply + updated session state |
| `GET` | `/oauth/callback` | Google OAuth redirect handler; exchanges code for tokens |
| `GET` | `/health` | Health check |
| `OPTIONS` | `/{proxy+}` | CORS preflight |

### POST /chat — Request Body
```json
{
  "message": "What do I have today?",
  "session_state": { ... }
}
```

### POST /chat — Response Body
```json
{
  "reply": "Here's what you have for today: ...",
  "session_state": { ... },
  "requires_auth": false
}
```

---

## Dependencies

```
google-api-python-client==2.131.0   Google Calendar API v3 client
google-auth==2.29.0                 Google OAuth 2.0 credentials
google-auth-httplib2==0.2.0         HTTP transport for google-auth
google-auth-oauthlib==1.2.0         OAuth flow helpers
boto3==1.34.84                      AWS SDK (Bedrock, SSM)
botocore==1.34.84                   AWS SDK core
```

---

## Requirements Traceability

| Requirement | Implemented In |
|-------------|---------------|
| FR-01 Calendar Read | `orchestrator._handle_read()`, `calendar_client.list_events()` |
| FR-02 Event Creation | `orchestrator._handle_create()`, `calendar_client.create_event()` |
| FR-03 Smart Slot Suggestion | `orchestrator._handle_suggest_slots()`, `calendar_client.find_free_slots()` |
| FR-04 Event Deletion | `orchestrator._handle_delete()`, `calendar_client.delete_event()` |
| FR-05 Event Rescheduling | `orchestrator._handle_update()`, `calendar_client.update_event()` |
| FR-06 Ambiguous Request Handling | `orchestrator.resolve_ambiguity()`, `orchestrator._resolve_pending_action()` |
| FR-07 Session Memory | `SessionState.conversation_history`, `orchestrator._append_to_history()` |
| FR-08 Google OAuth | `auth_manager.py`, `lambda_handler.handle_oauth_callback()` |
| FR-09 Confirmation Mode | `orchestrator.apply_confirmation()`, `SessionState.confirmation_mode` |
| FR-10 Working Hours | `orchestrator.update_session_preferences()`, `calendar_client.find_free_slots()` |
| FR-11 Error Handling | All modules — `RuntimeError` surfaced as user-friendly messages |
| NFR-01 AWS Free Tier | `infrastructure/template.yaml` — Lambda + API Gateway + SSM |
| NFR-02 Bedrock Model | `config.BEDROCK_MODEL_ID` env var |
| NFR-03 Rate Limiting | `calendar_client._execute_with_backoff()`, session event cache |
| NFR-05 Data Privacy | No calendar data persisted; tokens encrypted in SSM |
| NFR-06 Reliability | `auth_manager.refresh_access_token()`, `ReAuthRequiredException` |
| NFR-07 Maintainability | Separate modules, env var config, typed dataclasses |
