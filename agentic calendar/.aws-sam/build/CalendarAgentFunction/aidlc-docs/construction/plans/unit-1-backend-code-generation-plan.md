# Code Generation Plan — Unit 1: Backend Core

**Unit**: unit-1-backend
**Language**: Python 3.11
**Runtime**: AWS Lambda
**Code Location**: Workspace root (`backend/`, `infrastructure/`, `tests/`, `requirements.txt`)

---

## Unit Context

**Stories covered**: FR-01 through FR-11, NFR-01 through NFR-07
**Dependencies**: Amazon Bedrock, Google Calendar API v3, Google OAuth 2.0, AWS SSM
**Key design artifacts**: `aidlc-docs/inception/application-design/`

---

## Generation Steps

### Step 1: Project Structure Setup
- [x] Create `requirements.txt` with all Python dependencies
- [x] Create `backend/config.py` — environment variable loading and defaults

### Step 2: Shared Data Models
- [x] Create `backend/models.py` — all dataclasses: `CalendarEvent`, `CalendarEventInput`, `TimeSlot`, `BedrockResponse`, `OAuthTokens`, `SessionState`

### Step 3: Auth Manager
- [x] Create `backend/auth_manager.py` — OAuth code exchange, token storage in SSM, token retrieval, access token refresh, re-auth detection

### Step 4: Auth Manager Unit Tests
- [x] Create `tests/test_auth_manager.py` — tests for token exchange, storage, retrieval, refresh, and re-auth detection (with mocked SSM and Google OAuth)

### Step 5: Calendar Client
- [x] Create `backend/calendar_client.py` — list events (with session cache), create event (single + recurring), update event, delete event, find free slots, exponential backoff on 429

### Step 6: Calendar Client Unit Tests
- [x] Create `tests/test_calendar_client.py` — tests for all CRUD operations, cache behaviour, free slot finding, backoff (with mocked Google Calendar API)

### Step 7: Bedrock Client
- [x] Create `backend/bedrock_client.py` — system prompt construction, Bedrock Converse API invocation, response parsing into `BedrockResponse`

### Step 8: Bedrock Client Unit Tests
- [x] Create `tests/test_bedrock_client.py` — tests for prompt construction, invocation, response parsing, error handling (with mocked boto3 Bedrock client)

### Step 9: Agent Orchestrator
- [x] Create `backend/orchestrator.py` — `process_message()`, `resolve_ambiguity()`, `apply_confirmation()`, `update_session_preferences()`, `invalidate_event_cache()`, full intent routing logic

### Step 10: Orchestrator Unit Tests
- [x] Create `tests/test_orchestrator.py` — tests for each intent route (read, create, update, delete, suggest_slots, clarify, chat), ambiguity handling, confirmation mode, preference updates

### Step 11: API Handler (Lambda Entry Point)
- [x] Create `backend/lambda_handler.py` — `handle_chat()`, `handle_oauth_callback()`, `handle_health_check()`, top-level error handling, JSON serialization

### Step 12: Infrastructure — AWS SAM Template
- [x] Create `infrastructure/template.yaml` — AWS SAM template defining: Lambda function, API Gateway (POST /chat, GET /oauth/callback, GET /health), IAM role with SSM permissions, environment variables ✅

### Step 13: Deployment Script
- [x] Create `infrastructure/deploy.sh` — SAM build + deploy commands with parameter prompts ✅

### Step 14: Documentation Summary
- [x] Create `aidlc-docs/construction/unit-1-backend/code/code-summary.md` — summary of all generated files, module responsibilities, environment variables reference ✅

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL_ID` | Amazon Bedrock model ID | `amazon.nova-lite-v1:0` |
| `BEDROCK_REGION` | AWS region for Bedrock | `us-east-1` |
| `GOOGLE_CLIENT_ID` | Google OAuth app client ID | (required) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth app client secret | (required) |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | (required) |
| `SSM_TOKEN_PATH` | SSM parameter path for OAuth tokens | `/calendar-agent/oauth` |
| `DEFAULT_WORKING_HOURS_START` | Default working hours start | `09:00` |
| `DEFAULT_WORKING_HOURS_END` | Default working hours end | `18:00` |
| `DEFAULT_BUFFER_MINUTES` | Default buffer between meetings | `15` |
| `LOG_LEVEL` | Python logging level | `INFO` |
