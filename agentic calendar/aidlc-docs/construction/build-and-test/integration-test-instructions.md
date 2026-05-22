# Integration Test Instructions — Calendar-Agent

---

## Purpose

Integration tests validate that the backend components work together correctly when connected end-to-end — from the Lambda handler through the orchestrator to the external service clients. These tests use **SAM Local** to invoke the Lambda function locally and verify the full request/response cycle.

---

## Prerequisites

- AWS SAM CLI installed
- Docker installed and running (SAM Local uses Docker to emulate Lambda)
- Python virtual environment activated with dependencies installed
- `.env` file configured with test credentials (see build-instructions.md)

---

## Setup Integration Test Environment

### 1. Start SAM Local API

```bash
# From workspace root
sam local start-api \
  --template-file infrastructure/template.yaml \
  --env-vars .env.json \
  --port 3000

# The API will be available at http://localhost:3000
```

Create `.env.json` for SAM Local (maps env vars to the Lambda function):

```json
{
  "CalendarAgentFunction": {
    "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
    "BEDROCK_REGION": "us-east-1",
    "GOOGLE_CLIENT_ID": "your-client-id",
    "GOOGLE_CLIENT_SECRET": "your-client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:3000/oauth/callback",
    "SSM_TOKEN_PATH": "/calendar-agent/oauth-test",
    "AWS_REGION": "us-east-1",
    "LOG_LEVEL": "DEBUG",
    "FRONTEND_URL": "http://localhost:8080"
  }
}
```

### 2. Seed OAuth Tokens in SSM (for testing without real OAuth flow)

```bash
# Store test tokens in SSM so the integration tests can bypass the OAuth login
aws ssm put-parameter \
  --name "/calendar-agent/oauth-test" \
  --type "SecureString" \
  --value '{"access_token":"YOUR_REAL_ACCESS_TOKEN","refresh_token":"YOUR_REAL_REFRESH_TOKEN","expires_at":"2026-12-31T00:00:00+00:00"}' \
  --overwrite
```

> **Note**: For real integration testing, use a valid Google OAuth token from a test Google account.

---

## Test Scenarios

### Scenario 1: Health Check

**Description**: Verify the Lambda starts and responds to the health endpoint.

```bash
curl -s http://localhost:3000/health | python -m json.tool
```

**Expected**:
```json
{ "status": "ok" }
```

---

### Scenario 2: Chat — New Session (No Auth)

**Description**: Send a chat message without prior authentication. The backend should respond with `requires_auth: true`.

```bash
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What do I have today?"}' | python -m json.tool
```

**Expected** (when no tokens in SSM):
```json
{
  "reply": "It looks like you haven't connected your Google Calendar yet...",
  "session_state": { ... },
  "requires_auth": true
}
```

---

### Scenario 3: Chat — Read Events (With Auth)

**Description**: With valid OAuth tokens seeded in SSM, send a read request.

```bash
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What do I have today?"}' | python -m json.tool
```

**Expected**:
- `reply` contains a formatted list of today's events (or "no events" message)
- `session_state` is populated with conversation history
- `requires_auth` is absent or false

---

### Scenario 4: Chat — Create Event with Confirmation

**Description**: Request event creation with confirmation mode on (default).

```bash
# First message — request creation
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Block 2 hours for deep work tomorrow afternoon"}' | python -m json.tool

# Save the session_state from the response, then confirm:
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "1", "session_state": <PASTE_SESSION_STATE>}' | python -m json.tool

# Then confirm the creation:
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "yes", "session_state": <PASTE_SESSION_STATE>}' | python -m json.tool
```

**Expected**:
- First response: slot suggestions (2–3 options)
- Second response: confirmation prompt
- Third response: "Done! I've created **Deep Work**..."
- Event appears in the test Google Calendar

---

### Scenario 5: Chat — Delete Event

**Description**: Delete an existing event.

```bash
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Cancel my deep work block", "session_state": <PASTE_SESSION_STATE>}' | python -m json.tool
```

**Expected**:
- If one match: confirmation prompt → confirm → "Done! I've cancelled..."
- If multiple matches: disambiguation list

---

### Scenario 6: OAuth Callback

**Description**: Simulate the OAuth callback with a valid authorization code.

```bash
# This requires a real authorization code from Google (short-lived)
curl -s "http://localhost:3000/oauth/callback?code=REAL_AUTH_CODE&state=test" -v
```

**Expected**:
- HTTP 302 redirect to the frontend URL with `?auth=success`
- Tokens stored in SSM

---

### Scenario 7: Session State Round-Trip

**Description**: Verify session state is correctly serialised and deserialised across multiple turns.

```bash
# Turn 1
RESPONSE1=$(curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What do I have today?"}')

# Extract session_state
STATE=$(echo $RESPONSE1 | python -c "import sys,json; print(json.dumps(json.loads(sys.stdin.read())['session_state']))")

# Turn 2 — use the returned session state
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"And tomorrow?\", \"session_state\": $STATE}" | python -m json.tool
```

**Expected**:
- Turn 2 response includes conversation history from Turn 1
- No serialisation errors

---

## Cleanup

```bash
# Stop SAM Local (Ctrl+C in the terminal running it)

# Remove test tokens from SSM
aws ssm delete-parameter --name "/calendar-agent/oauth-test"

# Remove any test events created in Google Calendar (manual)
```

---

## Notes

- Integration tests require real AWS credentials (for SSM and Bedrock)
- Integration tests with Google Calendar require a real OAuth token from a test account
- For CI/CD, use mocked responses or a dedicated test Google account
- SAM Local cold starts may take 5–10 seconds on first invocation
