# 🗓️ Calendar-Agent

> An agentic AI assistant that fully manages your Google Calendar through a conversational web chat interface — powered by Amazon Bedrock and running on the AWS free tier.

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
Browser (S3 Static Site)
    │
    │  HTTPS REST
    ▼
AWS API Gateway
    │
    ▼
AWS Lambda (Python 3.11)
    ├── API Handler          — routing & serialisation
    ├── Agent Orchestrator   — conversation & intent routing
    ├── Bedrock Client       — NLU via Amazon Bedrock (Nova Lite)
    ├── Calendar Client      — Google Calendar API v3
    └── Auth Manager         — Google OAuth 2.0 + AWS SSM
```

**Everything runs on the AWS free tier.** No paid third-party services.

| Component | Service |
|-----------|---------|
| LLM | Amazon Bedrock (Nova Lite) |
| Backend | AWS Lambda + API Gateway |
| Token storage | AWS SSM Parameter Store |
| Frontend hosting | AWS S3 static website |
| Calendar | Google Calendar API v3 |
| Auth | Google OAuth 2.0 |

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
│   ├── style.css
│   └── app.js
├── infrastructure/
│   ├── template.yaml        # AWS SAM template
│   └── deploy.sh            # Deployment script
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

- Python 3.11+
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- A [Google Cloud project](https://console.cloud.google.com/) with the Calendar API enabled and an OAuth 2.0 client configured

### 1. Clone the repository

```bash
git clone https://github.com/your-username/calendar-agent.git
cd calendar-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the tests

```bash
python -m pytest tests/ -v
```

### 4. Deploy to AWS

```bash
chmod +x infrastructure/deploy.sh
./infrastructure/deploy.sh
```

The script will prompt you for:
- Google OAuth Client ID and Secret
- OAuth redirect URI
- Bedrock model ID (default: `amazon.nova-lite-v1:0`)

After deployment, the script outputs the API Gateway URL and the OAuth callback URL to register in Google Cloud Console.

### 5. Register the OAuth callback

In [Google Cloud Console](https://console.cloud.google.com/):
1. Go to **APIs & Services → Credentials**
2. Open your OAuth 2.0 Client
3. Add the `OAuthCallbackUrl` from the deployment output to **Authorised redirect URIs**

### 6. Deploy the frontend

Update `API_BASE_URL` in `frontend/app.js` with the `ApiBaseUrl` from the deployment output, then upload the `frontend/` folder to an S3 bucket with static website hosting enabled.

---

## Configuration

All configuration is managed via environment variables (set in `infrastructure/template.yaml` or your Lambda console):

| Variable | Default | Description |
|----------|---------|-------------|
| `BEDROCK_MODEL_ID` | `amazon.nova-lite-v1:0` | Bedrock model to use |
| `GOOGLE_CLIENT_ID` | *(required)* | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | *(required)* | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | *(required)* | OAuth callback URL |
| `SSM_TOKEN_PATH` | `/calendar-agent/oauth` | SSM path for token storage |
| `DEFAULT_BUFFER_MINUTES` | `15` | Default buffer between meetings |
| `DEFAULT_CONFIRMATION_MODE` | `true` | Ask before write/delete by default |

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
