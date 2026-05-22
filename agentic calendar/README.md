# 🗓️ Calendar-Agent

> An agentic AI assistant that fully manages your Google Calendar through a conversational web chat interface — powered by Amazon Bedrock (Nova Lite) and running on the AWS free tier.

---

## What is Calendar-Agent?

Calendar-Agent eliminates the daily overhead of manual scheduling. Instead of opening your calendar to check your day, create events, or resolve conflicts, you just chat with the agent in plain language and it handles everything autonomously.

The goal: reduce time spent on calendar management from ~30 minutes/day to under 5 minutes.

---

## Features

### 📋 Daily & Weekly Briefings
Ask *"What do I have today?"* or *"What's my week looking like?"* and get a structured summary of your events — including flagged conflicts and back-to-back meetings.

### ✏️ Natural Language Event Creation
Create single or recurring events without opening your calendar:
- *"Block 2 hours for deep work tomorrow afternoon"*
- *"Add a weekly team sync every Friday at 10am"*

### 🎯 Smart Time Slot Suggestions
When you don't specify an exact time, the agent finds the best available slots for you — respecting your working hours and leaving buffer time between meetings.

### 🗑️ Event Deletion & Rescheduling
Cancel or move events through chat:
- *"Cancel my 3pm meeting on Thursday"*
- *"Move my 1:1 to Friday morning"*

The agent always asks for confirmation before making changes (configurable).

### 🔍 Ambiguity Resolution
When a request could match multiple events, the agent presents all options and lets you choose — it never guesses and acts on the wrong event.

### ⚙️ Configurable Preferences
Set your preferences directly in the chat:
- *"My working hours are 8am to 5pm"*
- *"Add a 30-minute buffer between meetings"*
- *"Stop asking me to confirm every action"*

Preferences apply for the duration of your session.

---

## Architecture

```
Browser (local HTML or S3)
    │
    │  HTTPS REST
    ▼
AWS API Gateway          ← "The front door" — routes HTTP requests
    │
    ▼
AWS Lambda (Python 3.14) ← "The brain" — runs your code on demand
    ├── API Handler          — routing & serialisation
    ├── Agent Orchestrator   — conversation & intent routing
    ├── Bedrock Client       — NLU via Amazon Bedrock (Nova Lite)
    ├── Calendar Client      — Google Calendar API v3
    └── Auth Manager         — Google OAuth 2.0 + AWS SSM
```

### How the services work together

| Service | Role | What it does |
|---------|------|--------------|
| **API Gateway** | Front door | Receives HTTP requests from the browser, routes to Lambda |
| **Lambda** | Backend logic | Runs your Python code on demand — no server to manage |
| **Bedrock** | AI understanding | Converts natural language into structured actions |
| **SSM Parameter Store** | Token vault | Stores Google OAuth tokens encrypted — persistent login |
| **S3** *(optional)* | Frontend hosting | Serves the HTML/CSS/JS chat UI |
| **CloudFormation** | Infrastructure | Created all resources from `template.yaml` |
| **IAM Role** | Permissions | Gives Lambda access to Bedrock and SSM |

### Request flow

1. You type a message in the browser
2. Browser sends `POST /chat` to API Gateway
3. API Gateway triggers Lambda
4. Lambda gets your Google OAuth token from SSM
5. Lambda calls Bedrock → understands your intent
6. Lambda calls Google Calendar API → reads/writes events
7. Lambda returns the response through API Gateway
8. Browser displays the agent's reply

---

## Project Structure

```
calendar-agent/
├── backend/
│   ├── lambda_handler.py    # Lambda entry point
│   ├── orchestrator.py      # Agent logic & conversation management
│   ├── bedrock_client.py    # Amazon Bedrock integration
│   ├── calendar_client.py   # Google Calendar API integration
│   ├── auth_manager.py      # OAuth lifecycle & token storage
│   ├── models.py            # Shared data models
│   └── config.py            # Environment variable configuration
├── frontend/
│   ├── index.html           # Chat UI
│   ├── style.css            # Styles
│   └── app.js               # Frontend logic (OAuth, API calls, rendering)
├── infrastructure/
│   ├── template.yaml        # AWS SAM template
│   ├── deploy.sh            # Deployment script
│   └── destroy.sh           # Teardown script — deletes all AWS resources
├── tests/
│   ├── test_auth_manager.py
│   ├── test_bedrock_client.py
│   ├── test_calendar_client.py
│   └── test_orchestrator.py
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.14+ (or 3.11+)
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- A [Google Cloud project](https://console.cloud.google.com/) with Calendar API enabled and OAuth 2.0 credentials

> **Note**: Amazon Bedrock models auto-enable on first call — no manual model access step needed.

### 1. Clone and install

```bash
git clone https://github.com/your-username/calendar-agent.git
cd calendar-agent
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
pip install pytest
```

### 2. Run tests

```bash
pytest tests/ -v
```

All ~60 tests pass with no AWS or Google credentials needed (everything mocked).

### 3. Build

you need aws cli and add it to you variable env
```bash
winget install Amazon.SAM-CLI
```
```bash
sam build --template-file infrastructure/template.yaml
```

### 4. Deploy

```bash
sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```

SAM prompts for:
- Stack name (e.g. `sam-app`)
- Region (e.g. `eu-central-1`)
- Google OAuth Client ID and Secret
- Bedrock model ID (default: `amazon.nova-lite-v1:0`, use `eu.amazon.nova-lite-v1:0` for EU regions)

Answer **Y** to all "no authentication" prompts.

### 5. Get your API URL

```bash
aws cloudformation describe-stacks --stack-name sam-app --query "Stacks[0].Outputs" --output table
```

### 6. Register OAuth redirect URI

Copy the `OAuthCallbackUrl` from the outputs and add it to:
Google Cloud Console → APIs & Services → Credentials → your OAuth client → Authorised redirect URIs

### 7. Update frontend

Edit `frontend/app.js`:
- Set `API_BASE_URL` to your `ApiBaseUrl` from step 5
- Set `GOOGLE_CLIENT_ID` to your Google Client ID

### 8. Test it

Open `frontend/index.html` in your browser, sign in with Google, and start chatting.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Bedrock model (use `eu.amazon.nova-lite-v1:0` for EU) |
| `BEDROCK_REGION` | `us-east-1` | Region for Bedrock API calls |
| `GOOGLE_CLIENT_ID` | *(required)* | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | *(required)* | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | *(required)* | OAuth callback URL |
| `SSM_TOKEN_PATH` | `/calendar-agent/oauth` | SSM path for token storage |
| `DEFAULT_BUFFER_MINUTES` | `15` | Default buffer between meetings |
| `DEFAULT_CONFIRMATION_MODE` | `true` | Ask before write/delete by default |

---

## Destroy All Resources

To tear down everything:

```bash
sam delete --stack-name sam-app --region eu-central-1
```

Or use the script:

```bash
bash infrastructure/destroy.sh
```

This removes: Lambda, API Gateway, IAM role, SSM parameter, and CloudWatch logs.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ValidationException` from Bedrock | Use `eu.amazon.nova-lite-v1:0` for EU regions |
| `redirect_uri_mismatch` from Google | Register the exact callback URL in Google Cloud Console |
| `Missing Authentication Token` | You're hitting a path that doesn't exist (e.g. `/Prod` instead of `/Prod/health`) |
| `Forbidden` on root path | Normal — no route defined at `/`. Use `/health`, `/chat`, or `/oauth/callback` |
| Google consent shows "unverified app" | Click Advanced → Go to Calendar-Agent (unsafe) — normal for development |

---

## Roadmap

| Phase | Focus |
|-------|-------|
| **MVP** *(current)* | Single-user Google Calendar agent with web chat UI |
| **Phase 2** | Project follow-up tracking, team coordination, manager dashboard |
| **Phase 3** | Microsoft Outlook support, Jira/Notion integrations, multi-language |

---

## License

MIT
