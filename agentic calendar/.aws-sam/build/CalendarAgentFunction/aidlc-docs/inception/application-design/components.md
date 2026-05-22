# Components — Agentic Calendar Assistant

---

## Component Overview

The system is composed of five main components spanning the frontend and backend layers. Each component has a single, well-defined responsibility.

```
+---------------------------+
|   Web Chat UI             |  (Frontend — S3 static hosting)
|   Plain HTML/CSS/JS       |
+---------------------------+
            |  HTTPS (REST)
+---------------------------+
|   API Handler             |  (AWS Lambda + API Gateway)
|   Entry point / routing   |
+---------------------------+
            |
+---------------------------+
|   Agent Orchestrator      |  (AWS Lambda — core logic)
|   Conversation + intent   |
+---------------------------+
      |              |
+----------+   +------------------+
| Bedrock  |   | Calendar Client  |
| Client   |   | (Google Cal API) |
+----------+   +------------------+
                      |
              +------------------+
              |  Auth Manager    |
              |  (OAuth + SSM)   |
              +------------------+
```

---

## Component 1: Web Chat UI

**Type**: Frontend — Static Web Application

**Technology**: Plain HTML, CSS, JavaScript (no framework)

**Hosting**: AWS S3 static website hosting

**Responsibilities**:
- Render the conversational chat interface (message history, input field, send button)
- Display a loading/thinking indicator while awaiting agent response
- Send user messages to the backend API via HTTP POST
- Receive and display agent responses
- Initiate the Google OAuth 2.0 login flow on first use
- Handle OAuth redirect and pass the authorization code to the backend
- Maintain no application state beyond the current session's DOM

**Interfaces**:
- Outbound: REST calls to API Gateway endpoint
- Inbound: JSON responses from API Gateway

---

## Component 2: API Handler

**Type**: Backend — AWS Lambda Function (Python)

**Trigger**: AWS API Gateway (REST API)

**Responsibilities**:
- Receive and validate incoming HTTP requests from the frontend
- Route requests to the appropriate handler: chat message, OAuth callback, or health check
- Serialize/deserialize JSON request and response payloads
- Return structured HTTP responses with appropriate status codes
- Handle top-level error catching and return user-friendly error responses

**Interfaces**:
- Inbound: HTTP requests from API Gateway
- Outbound: Calls to Agent Orchestrator

---

## Component 3: Agent Orchestrator

**Type**: Backend — Core Logic Module (Python)

**Responsibilities**:
- Maintain the in-session conversation history (list of message turns)
- Receive the user's message and full conversation context
- Invoke the Bedrock Client to interpret user intent and determine the required action
- Dispatch the resolved action to the Calendar Client (read, create, update, delete)
- Apply session-level user preferences (confirmation mode, working hours, buffer time)
- Handle ambiguity resolution: detect when multiple events match and surface options to the user
- Format the final response to return to the API Handler
- Manage session-level in-memory event cache (invalidate on write operations)

**Interfaces**:
- Inbound: Calls from API Handler (user message + session state)
- Outbound: Calls to Bedrock Client, Calendar Client

---

## Component 4: Bedrock Client

**Type**: Backend — AWS Service Integration Module (Python)

**Responsibilities**:
- Construct prompts for Amazon Bedrock including system instructions, conversation history, and user message
- Invoke the Amazon Bedrock API (InvokeModel or Converse API)
- Parse the model's response to extract structured intent: action type, event parameters, clarification requests
- Handle Bedrock API errors and surface them to the Agent Orchestrator
- Manage model configuration (model ID, inference parameters) via environment variables

**Interfaces**:
- Inbound: Calls from Agent Orchestrator (conversation context + user message)
- Outbound: Amazon Bedrock API calls

---

## Component 5: Calendar Client

**Type**: Backend — Google API Integration Module (Python)

**Responsibilities**:
- Execute Google Calendar API v3 operations: list events, create event, update event, delete event
- Apply session-level event cache: return cached events on read, invalidate cache on write
- Implement exponential backoff on HTTP 429 (rate limit) responses
- Format raw Google Calendar API responses into clean, structured event objects
- Delegate OAuth token management to the Auth Manager

**Interfaces**:
- Inbound: Calls from Agent Orchestrator (action + parameters)
- Outbound: Google Calendar API v3, Auth Manager

---

## Component 6: Auth Manager

**Type**: Backend — Authentication Module (Python)

**Responsibilities**:
- Manage the Google OAuth 2.0 authorization code flow (exchange code for tokens)
- Store the OAuth access token and refresh token securely in AWS SSM Parameter Store or Secrets Manager
- Retrieve stored tokens and inject them into Google API calls
- Detect access token expiry and automatically refresh using the stored refresh token
- Detect invalid or revoked refresh tokens and signal the need for re-authentication to the Agent Orchestrator

**Interfaces**:
- Inbound: Calls from Calendar Client (token retrieval/refresh requests), API Handler (OAuth callback)
- Outbound: Google OAuth 2.0 endpoints, AWS SSM Parameter Store / Secrets Manager
