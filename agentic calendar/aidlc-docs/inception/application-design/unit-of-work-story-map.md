# Unit of Work Story Map — Agentic Calendar Assistant

## Unit 1 — Backend Core

| Requirement | Description | Component |
|-------------|-------------|-----------|
| FR-01 | Calendar Read — Daily and Weekly Briefing | Calendar Client + Orchestrator |
| FR-02 | Event Creation via Natural Language | Calendar Client + Orchestrator + Bedrock Client |
| FR-03 | Smart Time Slot Suggestion | Calendar Client + Orchestrator + Bedrock Client |
| FR-04 | Event Deletion | Calendar Client + Orchestrator + Bedrock Client |
| FR-05 | Event Rescheduling | Calendar Client + Orchestrator + Bedrock Client |
| FR-06 | Ambiguous Request Handling | Orchestrator + Bedrock Client |
| FR-07 | Session-Level Conversation Memory | Orchestrator (SessionState) |
| FR-08 | Google OAuth 2.0 Authentication | Auth Manager + API Handler |
| FR-09 | User-Configurable Confirmation Mode | Orchestrator (PreferenceService) |
| FR-10 | User-Configurable Working Hours | Orchestrator (PreferenceService) |
| FR-11 | Error Handling — API Failures | All backend components |
| NFR-01 | AWS Free Tier Compliance | Infrastructure (SAM template) |
| NFR-02 | Bedrock Model Selection | Bedrock Client (env var config) |
| NFR-03 | Google Calendar API Rate Limiting | Calendar Client (cache + backoff) |
| NFR-05 | Data Privacy | All backend components |
| NFR-06 | Reliability (token refresh) | Auth Manager |
| NFR-07 | Maintainability (Python modules) | All backend components |

## Unit 2 — Frontend

| Requirement | Description | Component |
|-------------|-------------|-----------|
| FR-08 | Google OAuth login initiation | app.js (OAuth redirect) |
| FR-12 | Web Chat Interface | index.html + style.css + app.js |
| NFR-04 | Performance (loading indicator) | app.js |
