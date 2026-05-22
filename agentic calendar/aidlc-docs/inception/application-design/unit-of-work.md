# Units of Work — Agentic Calendar Assistant

---

## Decomposition Strategy

The system is decomposed into **2 units** aligned with the two deployment artifacts: the backend Lambda function and the frontend static web application. This split allows each unit to be developed, tested, and deployed independently.

---

## Unit 1: Backend Core

**Unit ID**: `unit-1-backend`

**Description**: The complete AWS Lambda backend — all Python modules, the AWS SAM infrastructure template, and unit tests.

**Responsibilities**:
- API Handler (Lambda entry point, routing)
- Agent Orchestrator (conversation management, intent routing, session state)
- Bedrock Client (Amazon Bedrock NLU integration)
- Calendar Client (Google Calendar API v3 integration, session cache)
- Auth Manager (Google OAuth 2.0 lifecycle, AWS SSM token storage)
- Shared data models
- Configuration management (environment variables)
- AWS SAM / CloudFormation template (Lambda + API Gateway + SSM)
- Unit tests for all modules

**Code Location**: `backend/` and `infrastructure/` in workspace root

**Key Files**:
```
backend/
├── lambda_handler.py
├── orchestrator.py
├── bedrock_client.py
├── calendar_client.py
├── auth_manager.py
├── models.py
└── config.py
infrastructure/
├── template.yaml        (AWS SAM)
└── deploy.sh
tests/
├── test_orchestrator.py
├── test_bedrock_client.py
├── test_calendar_client.py
└── test_auth_manager.py
requirements.txt
```

**External Dependencies**:
- Amazon Bedrock API
- Google Calendar API v3
- Google OAuth 2.0
- AWS SSM Parameter Store / Secrets Manager

---

## Unit 2: Frontend

**Unit ID**: `unit-2-frontend`

**Description**: The static web chat interface — plain HTML, CSS, and JavaScript deployed to AWS S3.

**Responsibilities**:
- Chat UI rendering (message history, input field, send button, loading indicator)
- Session state management in browser memory (JavaScript variable)
- HTTP communication with the backend API Gateway endpoint
- Google OAuth login flow initiation and redirect handling
- S3 deployment configuration

**Code Location**: `frontend/` in workspace root

**Key Files**:
```
frontend/
├── index.html
├── style.css
└── app.js
```

**External Dependencies**:
- Backend API Gateway endpoint (Unit 1)

---

## Unit Dependencies

| Unit | Depends On | Nature |
|------|-----------|--------|
| Unit 1 — Backend Core | Amazon Bedrock, Google Calendar API, Google OAuth, AWS SSM | External services |
| Unit 2 — Frontend | Unit 1 (API Gateway endpoint URL) | Runtime dependency |

**Development order**: Unit 1 must be deployed before Unit 2 can be fully tested end-to-end. However, Unit 2 can be developed in parallel using a mock API endpoint.
