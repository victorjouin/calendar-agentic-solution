# Build & Deploy Instructions — Calendar-Agent

---

## Prerequisites (one-time setup)

| Tool | Install |
|------|---------|
| Python 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| AWS CLI v2 | [AWS install guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| AWS SAM CLI | `pip install aws-sam-cli` |
| Git | Any version |

---

## Step 1: Configure AWS CLI

```bash
aws configure
```

Enter:
- Access Key ID
- Secret Access Key
- Default region: `us-east-1`
- Output format: `json`

> **Note on Bedrock**: Amazon Nova Lite is auto-enabled — no manual model access step required. The first API call auto-subscribes your account.

---

## Step 2: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. **Enable the Google Calendar API**:
   - APIs & Services → Library → search "Google Calendar API" → Enable
4. **Create OAuth 2.0 credentials**:
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Web application**
   - Name: `Calendar-Agent`
   - Authorised redirect URIs: **leave blank for now** (added after step 7)
5. Copy the **Client ID** and **Client Secret** — you'll need them in step 6

---

## Step 3: Clone and Install Dependencies

```bash
git clone https://github.com/your-username/calendar-agent.git
cd calendar-agent

# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest
```

---

## Step 4: Run Unit Tests

```bash
pytest tests/ -v
```

All ~60 tests should pass. No AWS or Google credentials needed — everything is mocked.

---

## Step 5: Build the Lambda Package

```bash
sam build --template-file infrastructure/template.yaml
```

Expected output: `Build Succeeded`

---

## Step 6: Deploy the Backend to AWS

```bash
sam deploy --guided
```

SAM will prompt you interactively:

| Prompt | What to enter |
|--------|---------------|
| Stack Name | `calendar-agent` |
| AWS Region | `us-east-1` |
| Parameter GoogleClientId | Your Google Client ID from step 2 |
| Parameter GoogleClientSecret | Your Google Client Secret from step 2 |
| Parameter GoogleRedirectUri | Leave blank (press Enter) — updated in step 8 |
| Parameter BedrockModelId | Press Enter for default (`amazon.nova-lite-v1:0`) |
| Parameter FrontendUrl | Leave blank (press Enter) — updated in step 12 |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `y` |
| Save arguments to samconfig.toml | `y` |

Wait for `CREATE_COMPLETE` (~3–5 minutes).

---

## Step 7: Get the Stack Outputs

```bash
aws cloudformation describe-stacks --stack-name calendar-agent --query "Stacks[0].Outputs" --output table
```

Note these values:
- **ApiBaseUrl** → e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/Prod`
- **OAuthCallbackUrl** → e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/Prod/oauth/callback`

---

## Step 8: Register the OAuth Redirect URI in Google

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click your OAuth 2.0 Client
3. Under **Authorised redirect URIs**, add the `OAuthCallbackUrl` from step 7
4. Save

---

## Step 9: Re-deploy with the Correct Redirect URI

```bash
sam deploy \
  --stack-name calendar-agent \
  --parameter-overrides \
    GoogleClientId=YOUR_CLIENT_ID \
    GoogleClientSecret=YOUR_CLIENT_SECRET \
    GoogleRedirectUri=https://abc123.execute-api.us-east-1.amazonaws.com/Prod/oauth/callback \
  --no-fail-on-empty-changeset \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --resolve-s3
```

---

## Step 10: Update the Frontend Configuration

Open `frontend/app.js` and replace the two placeholder values:

```javascript
// Line 12 — replace with your ApiBaseUrl from step 7
const API_BASE_URL = 'https://abc123.execute-api.us-east-1.amazonaws.com/Prod';

// Line 16 — replace with your Google Client ID from step 2
const GOOGLE_CLIENT_ID = 'your-client-id.apps.googleusercontent.com';
```

---

## Step 11: Create an S3 Bucket for the Frontend

```bash
# Replace YOURNAME with something unique (bucket names are global)
aws s3 mb s3://calendar-agent-frontend-YOURNAME --region us-east-1

# Enable static website hosting
aws s3 website s3://calendar-agent-frontend-YOURNAME --index-document index.html

# Allow public read access
aws s3api put-public-access-block \
  --bucket calendar-agent-frontend-YOURNAME \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy \
  --bucket calendar-agent-frontend-YOURNAME \
  --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::calendar-agent-frontend-YOURNAME/*\"}]}"
```

---

## Step 12: Upload the Frontend and Final Backend Update

```bash
# Upload frontend files to S3
aws s3 sync frontend/ s3://calendar-agent-frontend-YOURNAME --delete
```

Your frontend URL: `http://calendar-agent-frontend-YOURNAME.s3-website-us-east-1.amazonaws.com`

Now update the backend with the frontend URL so OAuth redirects work:

```bash
sam deploy \
  --stack-name calendar-agent \
  --parameter-overrides \
    GoogleClientId=YOUR_CLIENT_ID \
    GoogleClientSecret=YOUR_CLIENT_SECRET \
    GoogleRedirectUri=https://abc123.execute-api.us-east-1.amazonaws.com/Prod/oauth/callback \
    FrontendUrl=http://calendar-agent-frontend-YOURNAME.s3-website-us-east-1.amazonaws.com \
  --no-fail-on-empty-changeset \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --resolve-s3
```

---

## Step 13: Verify Everything Works

1. Open your frontend URL in a browser
2. Click **"Sign in with Google"**
3. Grant calendar access on the Google consent screen
4. You should land on the chat screen
5. Type **"What do I have today?"** — you should see your calendar events

---

## Quick Verification Checklist

```bash
# Health check
curl https://YOUR-API-URL/Prod/health
# Expected: {"status": "ok"}

# Frontend loads
curl -s http://calendar-agent-frontend-YOURNAME.s3-website-us-east-1.amazonaws.com | head -5
# Expected: <!DOCTYPE html>
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: No module named 'backend'` | Running from wrong directory | Run all commands from workspace root |
| SAM build fails | Template path wrong | Use `--template-file infrastructure/template.yaml` |
| `AccessDeniedException` from Bedrock | IAM permissions missing | Check Lambda role has `bedrock:InvokeModel` and `bedrock:Converse` (SAM template handles this) |
| `redirect_uri_mismatch` from Google | URI not registered | Add the exact `OAuthCallbackUrl` to Google Cloud Console (step 8) |
| Frontend shows CORS error | API Gateway CORS not configured | The SAM template handles CORS — redeploy if needed |
| `ParameterNotFound` from SSM | First-time use, no tokens yet | Normal — user needs to sign in via OAuth first |
| Google consent screen shows "unverified app" | App not verified by Google | Click "Advanced" → "Go to Calendar-Agent (unsafe)" — normal for development |

---

## Summary of URLs

| What | Where |
|------|-------|
| Frontend | `http://calendar-agent-frontend-YOURNAME.s3-website-us-east-1.amazonaws.com` |
| Backend API | `https://abc123.execute-api.us-east-1.amazonaws.com/Prod` |
| OAuth Callback | `https://abc123.execute-api.us-east-1.amazonaws.com/Prod/oauth/callback` |
| Health Check | `https://abc123.execute-api.us-east-1.amazonaws.com/Prod/health` |

---

## Total Deployment Time

~15–20 minutes (mostly waiting for CloudFormation stack creation).
