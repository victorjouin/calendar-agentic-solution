# Unit of Work Dependencies — Agentic Calendar Assistant

## Dependency Matrix

| Unit | Depends On | Type | Notes |
|------|-----------|------|-------|
| Unit 1 — Backend Core | Amazon Bedrock | External service | boto3 SDK |
| Unit 1 — Backend Core | Google Calendar API v3 | External service | google-api-python-client |
| Unit 1 — Backend Core | Google OAuth 2.0 | External service | google-auth library |
| Unit 1 — Backend Core | AWS SSM / Secrets Manager | External service | boto3 SDK |
| Unit 2 — Frontend | Unit 1 API Gateway endpoint | Runtime | URL injected at deploy time |

## Build Order
1. **Unit 1** — Backend Core (no internal dependencies)
2. **Unit 2** — Frontend (requires Unit 1 API Gateway URL for full E2E testing)

## Parallel Development
Both units can be developed in parallel. Unit 2 uses a placeholder API URL during development, replaced with the real API Gateway URL at deployment time.
