# Requirements Document — Agentic Calendar Assistant

---

## Intent Analysis Summary

| Field | Value |
|-------|-------|
| **User Request** | Build a single-user agentic Google Calendar assistant with a web chat UI, running on AWS free tier with Amazon Bedrock as the LLM provider |
| **Request Type** | New Project (Greenfield) |
| **Scope Estimate** | System-wide — multiple components (frontend, backend, LLM integration, Google Calendar API, OAuth) |
| **Complexity Estimate** | Complex — agentic reasoning, external API integrations, OAuth flow, serverless infrastructure |
| **Depth Level** | Comprehensive |

---

## 1. Project Overview

Calendar-Agent is a single-user agentic assistant that autonomously manages a user's Google Calendar through a conversational web chat interface. The agent reads, creates, updates, and deletes calendar events on the user's behalf using natural language, powered by Amazon Bedrock. The system runs entirely on the AWS free tier.

**Target User**: Individual contributor (employee) with a busy calendar who wants to delegate scheduling and planning to an AI assistant.

**Primary Goal**: Reduce time spent on manual calendar management from ~30 minutes/day to under 5 minutes/day.

---

## 2. Functional Requirements

### FR-01: Calendar Read — Daily and Weekly Briefing

**Description**: The agent shall fetch and display the user's upcoming calendar events from Google Calendar.

**Acceptance Criteria**:
- The agent shall retrieve events for the current day when the user asks "What do I have today?" or equivalent
- The agent shall retrieve events for the current week when the user asks "What's my week looking like?" or equivalent
- The agent shall present events in a structured, readable format including event title, date, start time, end time, and location (if available)
- The agent shall detect and flag scheduling conflicts (overlapping events) in the summary
- The agent shall detect and flag back-to-back meetings with no buffer time in the summary

### FR-02: Event Creation via Natural Language

**Description**: The agent shall create new calendar events based on natural language instructions from the user.

**Acceptance Criteria**:
- The agent shall parse natural language event creation requests (e.g., "Block 2 hours for deep work tomorrow afternoon")
- The agent shall extract event title, duration, and preferred time window from the user's request
- The agent shall create the event in Google Calendar via the Google Calendar API
- The agent shall support creation of single one-off events
- The agent shall support creation of recurring events (e.g., "every Monday at 9am", "weekly team sync on Fridays")
- The agent shall confirm successful creation by echoing back the event details (title, date, time)
- The agent shall not require the user to open Google Calendar directly

### FR-03: Smart Time Slot Suggestion

**Description**: When the user requests scheduling without specifying an exact time, the agent shall propose optimal available time slots.

**Acceptance Criteria**:
- The agent shall check the user's calendar for free slots within the requested time window
- The agent shall respect the user's configured working hours when suggesting slots (see FR-10)
- The agent shall avoid suggesting slots that create back-to-back meetings — a configurable buffer time shall be applied between events
- The agent shall propose 2–3 slot options with a brief rationale for each
- The agent shall allow the user to select one of the proposed slots or ask for alternatives
- The agent shall create the event in the selected slot upon user confirmation

### FR-04: Event Deletion

**Description**: The agent shall delete calendar events on the user's behalf.

**Acceptance Criteria**:
- The agent shall identify the target event based on the user's natural language description (e.g., "Cancel my 3pm meeting on Thursday")
- When multiple events match the description, the agent shall present all matching options and ask the user to choose before taking any action
- The agent shall apply the user's configured confirmation preference before executing the deletion (see FR-09)
- The agent shall delete the event via the Google Calendar API upon confirmation
- The agent shall confirm successful deletion to the user

### FR-05: Event Rescheduling

**Description**: The agent shall move an existing calendar event to a new time slot.

**Acceptance Criteria**:
- The agent shall identify the target event based on the user's natural language description
- When multiple events match the description, the agent shall present all matching options and ask the user to choose
- The agent shall apply the user's configured confirmation preference before executing the reschedule (see FR-09)
- The agent shall update the event's start and end time in Google Calendar via the API
- The agent shall confirm the new event time to the user after successful rescheduling

### FR-06: Ambiguous Request Handling

**Description**: When the user's request matches multiple calendar events, the agent shall present all matching options and let the user choose.

**Acceptance Criteria**:
- The agent shall detect ambiguity when a natural language request matches more than one event
- The agent shall present a numbered or labelled list of all matching events with their date and time
- The agent shall ask the user to select the intended event before proceeding with any action
- The agent shall not take any write or delete action until the user has resolved the ambiguity

### FR-07: Session-Level Conversation Memory

**Description**: The agent shall maintain context within a single conversation session.

**Acceptance Criteria**:
- The agent shall retain the full conversation history within an active session
- The agent shall use prior turns in the session to resolve references (e.g., "reschedule that one" referring to an event discussed earlier in the same session)
- The agent shall NOT persist conversation history across sessions — each new session starts fresh
- The agent shall NOT require the user to re-specify context that was already established earlier in the same session

### FR-08: Google OAuth 2.0 Authentication

**Description**: The user shall authenticate with Google via OAuth 2.0 to grant the agent access to their Google Calendar.

**Acceptance Criteria**:
- The web chat UI shall present a "Sign in with Google" flow on first use
- The agent shall request only the minimum required Google Calendar API scopes
- Upon successful authentication, the OAuth access token and refresh token shall be stored securely in AWS (SSM Parameter Store or Secrets Manager)
- The agent shall automatically refresh the access token using the stored refresh token when it expires
- The agent shall prompt the user to re-authenticate if the refresh token is invalid or revoked
- The user shall not need to re-authenticate on every session as long as the stored token remains valid

### FR-09: User-Configurable Confirmation Mode

**Description**: The user shall be able to configure whether the agent asks for confirmation before executing write or delete operations.

**Acceptance Criteria**:
- The agent shall support two confirmation modes: **confirmation on** (agent asks before every write/delete) and **confirmation off** (agent executes immediately)
- The default confirmation mode shall be **confirmation on**
- The user shall be able to change the confirmation mode via a natural language command in the chat (e.g., "Stop asking me to confirm every action")
- The configured preference shall persist for the duration of the session
- Regardless of confirmation mode, the agent shall always ask for clarification when a request is ambiguous (see FR-06)

### FR-10: User-Configurable Working Hours

**Description**: The user shall be able to configure their working hours, which the agent uses when suggesting time slots.

**Acceptance Criteria**:
- The agent shall default to 9:00am–6:00pm Monday–Friday if no working hours have been configured
- The user shall be able to set their working hours via a natural language command in the chat (e.g., "My working hours are 8am to 5pm")
- The agent shall only suggest time slots within the user's configured working hours
- The configured working hours shall persist for the duration of the session

### FR-11: Error Handling — API Failures and Bedrock Unavailability

**Description**: The agent shall handle external service failures gracefully.

**Acceptance Criteria**:
- When Amazon Bedrock is unavailable or returns an error, the agent shall display a friendly error message and ask the user to retry
- When the Google Calendar API returns an error, the agent shall display a descriptive error message indicating what failed
- The agent shall NOT silently fail or produce incorrect results when an external service is unavailable
- The agent shall NOT retry automatically — the user shall be informed and asked to retry manually

### FR-12: Web Chat Interface

**Description**: All user interactions with the agent shall occur through a web-based chat interface.

**Acceptance Criteria**:
- The chat UI shall be built with plain HTML, CSS, and JavaScript — no frontend framework required
- The UI shall display a scrollable conversation history showing user messages and agent responses
- The UI shall provide a text input field and a send button for user messages
- The UI shall be accessible via a web browser without requiring any local installation
- The UI shall be deployed and hosted on AWS (S3 static hosting or equivalent free-tier option)
- The UI shall display a loading/thinking indicator while the agent is processing a request

---

## 3. Non-Functional Requirements

### NFR-01: AWS Free Tier Compliance

- All infrastructure components shall operate within AWS free tier limits
- The system shall use AWS Lambda + API Gateway for the serverless backend
- The system shall use Amazon Bedrock for LLM inference (free tier / on-demand pricing)
- The system shall use AWS SSM Parameter Store or Secrets Manager for token storage
- No paid third-party services shall be used

### NFR-02: Amazon Bedrock Model Selection

- The agent shall use the best available Amazon Bedrock model within the free tier
- Recommended default: **Amazon Nova Lite** (fast, cost-efficient, suitable for conversational tasks)
- The model selection shall be configurable without code changes (environment variable or config)
- The system shall be designed to swap models easily if a better free-tier option becomes available

### NFR-03: Google Calendar API Rate Limiting

- The system shall implement session-level in-memory caching of calendar events to reduce API call frequency
- Cached data shall be invalidated when the agent performs a write operation (create, update, delete) on the calendar
- The system shall implement exponential backoff on Google Calendar API rate limit errors (HTTP 429)

### NFR-04: Performance

- The agent shall respond to user messages within 10 seconds under normal operating conditions
- Calendar read operations shall complete within 5 seconds
- The system shall handle one concurrent user (single-user MVP)

### NFR-05: Data Privacy

- Calendar event content sent to Amazon Bedrock shall not be persisted beyond the active Lambda invocation
- No raw calendar event data shall be stored in any database or persistent storage
- OAuth tokens shall be stored encrypted in AWS SSM Parameter Store or Secrets Manager

### NFR-06: Reliability

- The system shall implement token refresh logic to prevent silent OAuth failures
- The system shall surface all errors to the user with actionable messages
- The system shall not lose conversation context within an active session due to transient errors

### NFR-07: Maintainability

- The backend shall be implemented in Python (compatible with AWS Lambda runtime)
- Code shall be structured in clearly separated modules: API handler, agent logic, Google Calendar client, Bedrock client
- All configuration (model ID, working hours default, API endpoints) shall be managed via environment variables

---

## 4. User Scenarios and Edge Cases

### Scenario 1: Happy Path — Daily Briefing
- User opens chat, asks "What do I have today?"
- Agent fetches today's events, returns structured summary with any conflicts flagged
- **Expected**: Clean summary in under 5 seconds

### Scenario 2: Smart Scheduling with Slot Suggestion
- User asks "Block 2 hours for deep work tomorrow afternoon"
- Agent checks free slots in the afternoon respecting working hours and buffer rules
- Agent proposes 2–3 options; user picks one; agent creates event and confirms
- **Expected**: Event appears in Google Calendar

### Scenario 3: Ambiguous Delete
- User says "Cancel my meeting tomorrow" — two meetings exist tomorrow
- Agent presents both options with times; user selects one; agent confirms and deletes
- **Expected**: Only the selected event is deleted

### Scenario 4: Recurring Event Creation
- User says "Add a weekly team sync every Friday at 10am"
- Agent creates a recurring event in Google Calendar
- **Expected**: Recurring event series created correctly

### Scenario 5: Confirmation Mode Toggle
- User says "Stop asking me to confirm every action"
- Agent acknowledges and switches to no-confirmation mode for the session
- User creates an event — agent executes without asking for confirmation
- **Expected**: Seamless execution without confirmation prompt

### Scenario 6: Bedrock Unavailable
- Bedrock returns a 503 error
- Agent displays: "I'm having trouble connecting to my AI service right now. Please try again in a moment."
- **Expected**: No silent failure; user is informed

### Scenario 7: OAuth Token Expiry
- Access token expires mid-session
- Agent automatically refreshes using stored refresh token
- Interaction continues without interruption
- **Expected**: Transparent token refresh; user unaware

### Scenario 8: Working Hours Configuration
- User says "My working hours are 8am to 5pm"
- Agent acknowledges and uses these hours for all subsequent slot suggestions in the session
- **Expected**: No slots suggested outside 8am–5pm

---

## 5. Integration Points

| Integration | Purpose | Notes |
|-------------|---------|-------|
| Google Calendar API v3 | Read, create, update, delete events | Requires OAuth 2.0 app registration |
| Google OAuth 2.0 | User authentication and calendar access | Requires app approval for calendar scopes |
| Amazon Bedrock | LLM natural language understanding and reasoning | Default model: Amazon Nova Lite |
| AWS Lambda | Serverless backend execution | Python runtime |
| AWS API Gateway | HTTP endpoint for frontend-to-backend communication | REST API |
| AWS SSM Parameter Store / Secrets Manager | Secure OAuth token storage | Encrypted at rest |
| AWS S3 (or equivalent) | Static hosting for web chat UI | Free tier |

---

## 6. Out of Scope (MVP)

| Feature | Reason | Target Phase |
|---------|--------|--------------|
| Multi-user / team coordination | Single-user validates core value first | Phase 2 |
| Manager dashboard | Requires multi-user support | Phase 2 |
| Project follow-up tracking | Needs event tagging system | Phase 2 |
| Proactive push notifications | Requires background process | Phase 2 |
| Mobile app | Web UI sufficient for MVP | Phase 2 |
| Outlook / Office 365 | Google Calendar validates approach first | Phase 3 |
| PM tool integrations (Jira, Notion) | Out of scope for calendar-only MVP | Phase 3 |
| Cross-session persistent memory | Session-only memory sufficient for MVP | Phase 2 |
| User-defined scheduling preferences beyond working hours | Complexity deferred | Phase 2 |

---

## 7. Constraints and Assumptions

| Item | Detail | Risk if Wrong |
|------|--------|---------------|
| AWS free tier sufficient | Single-user load stays within Lambda, API Gateway, and Bedrock free tier limits | Costs incurred; add usage caps |
| Google Calendar API quota sufficient | Single-user usage stays within free quota | Rate limiting; session cache mitigates |
| Bedrock Nova Lite sufficient | Model handles conversational calendar tasks adequately | Switch to Nova Pro or Claude if needed |
| Single OAuth user | One user authenticates; token stored in SSM | Multi-user support deferred to Phase 2 |
| User initiates all interactions | No proactive push notifications in MVP | Accepted limitation |

---

## 8. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time spent on manual scheduling | < 5 min/day | User self-report |
| Scheduling conflicts per week | 0 unresolved | Calendar audit |
| Agent task completion rate | > 90% of requests handled correctly | Interaction logs |
| User satisfaction | > 4/5 rating | Post-session feedback |
| System cost | $0 (free tier) | AWS billing dashboard |

---

## 9. Extension Configuration

| Extension | Status | Decision |
|-----------|--------|----------|
| Security Baseline | **Disabled** | PoC/prototype — security rules not enforced |
| Property-Based Testing | **Disabled** | Not required for this project scope |
