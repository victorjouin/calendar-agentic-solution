# Component Dependencies — Agentic Calendar Assistant

---

## Dependency Matrix

| Component | Depends On | Communication Pattern |
|-----------|-----------|----------------------|
| Web Chat UI | API Handler (via API Gateway) | HTTP REST (JSON) |
| API Handler | Agent Orchestrator | Direct Python function call (same Lambda) |
| Agent Orchestrator | Bedrock Client | Direct Python function call (same Lambda) |
| Agent Orchestrator | Calendar Client | Direct Python function call (same Lambda) |
| Agent Orchestrator | Auth Manager | Indirect (via Calendar Client) |
| Calendar Client | Auth Manager | Direct Python function call (same Lambda) |
| Calendar Client | Google Calendar API v3 | HTTPS REST |
| Auth Manager | Google OAuth 2.0 | HTTPS REST |
| Auth Manager | AWS SSM / Secrets Manager | AWS SDK (boto3) |
| Bedrock Client | Amazon Bedrock | AWS SDK (boto3) |

---

## Dependency Diagram

```
+-------------------+
|   Web Chat UI     |
|   (S3 Static)     |
+-------------------+
         |
         | HTTPS REST (JSON)
         v
+-------------------+       AWS API Gateway
|   API Handler     |<-------(trigger)
|   (Lambda)        |
+-------------------+
         |
         | function call
         v
+-------------------+
|  Agent            |
|  Orchestrator     |
+-------------------+
    |           |
    | call      | call
    v           v
+----------+ +------------------+
| Bedrock  | | Calendar Client  |
| Client   | |                  |
+----------+ +------------------+
    |               |
    | boto3         | function call
    v               v
+----------+ +------------------+
| Amazon   | |  Auth Manager    |
| Bedrock  | |                  |
+----------+ +------------------+
                  |         |
            boto3 |         | HTTPS
                  v         v
           +--------+  +----------+
           | AWS    |  | Google   |
           | SSM /  |  | OAuth    |
           | Secrets|  | 2.0      |
           +--------+  +----------+

Calendar Client also calls:
+----------------------+
| Google Calendar API  |
| v3 (HTTPS REST)      |
+----------------------+
```

---

## Data Flow — Chat Message Turn

```
1. User types message in Web Chat UI
2. UI sends POST /chat { session_id, message, session_state } to API Gateway
3. API Gateway triggers Lambda → API Handler.handle_chat()
4. API Handler calls Agent Orchestrator.process_message()
5. Orchestrator calls PreferenceService.detect_preference_change() → updates session state
6. Orchestrator calls BedrockClient.invoke() with conversation history + system prompt
7. Bedrock Client calls Amazon Bedrock API → returns structured intent
8. Orchestrator routes intent:
   a. Read action → Calendar Client.list_events()
      → Auth Manager.get_valid_access_token() → SSM/Secrets Manager
      → Google Calendar API v3
   b. Write/delete action → [confirmation check] → Calendar Client.create/update/delete_event()
      → Auth Manager.get_valid_access_token()
      → Google Calendar API v3
      → Calendar Client invalidates event cache
9. Orchestrator formats reply, updates conversation history in session state
10. API Handler returns { reply, session_state } to API Gateway
11. API Gateway returns HTTP 200 to Web Chat UI
12. UI renders agent reply in chat window
```

---

## Data Flow — OAuth Login

```
1. User clicks "Sign in with Google" in Web Chat UI
2. UI redirects to Google OAuth consent screen
3. User grants calendar access
4. Google redirects to /oauth/callback?code=...&state=...
5. API Gateway triggers Lambda → API Handler.handle_oauth_callback()
6. API Handler calls Auth Manager.exchange_code_for_tokens(code)
7. Auth Manager calls Google OAuth token endpoint → receives access + refresh tokens
8. Auth Manager calls AWS SSM/Secrets Manager to store tokens (encrypted)
9. API Handler returns { authenticated: true } to UI
10. UI enables chat interface
```

---

## Coupling Analysis

| Coupling | Type | Notes |
|----------|------|-------|
| API Handler ↔ Agent Orchestrator | Tight (same Lambda) | Acceptable — single deployable unit for MVP |
| Agent Orchestrator ↔ Bedrock Client | Tight (same Lambda) | Model swappable via env var |
| Agent Orchestrator ↔ Calendar Client | Tight (same Lambda) | Clean interface via typed methods |
| Calendar Client ↔ Google Calendar API | Loose (HTTP) | Isolated in Calendar Client module |
| Auth Manager ↔ AWS SSM | Loose (SDK) | Parameter names configurable via env vars |
| Web Chat UI ↔ API Gateway | Loose (HTTP REST) | API contract defined by JSON schema |

---

## External Dependencies

| External Service | Owner | Failure Impact | Mitigation |
|-----------------|-------|----------------|------------|
| Google Calendar API v3 | Google | Calendar operations fail | Exponential backoff; user-facing error message |
| Google OAuth 2.0 | Google | Authentication fails | Token refresh; re-auth prompt |
| Amazon Bedrock | AWS | All NLU fails | User-facing error; ask to retry |
| AWS SSM / Secrets Manager | AWS | Token retrieval fails | User-facing error; re-auth prompt |
| AWS API Gateway | AWS | All requests fail | AWS managed SLA |
| AWS Lambda | AWS | All backend fails | AWS managed SLA |
