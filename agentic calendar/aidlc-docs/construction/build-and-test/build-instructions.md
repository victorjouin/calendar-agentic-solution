# Build Instructions — Calendar-Agent

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Lambda runtime version |
| pip | Latest | `python -m pip install --upgrade pip` |
| AWS CLI | v2 | `aws configure` must be run |
| AWS SAM CLI | Latest | `pip install aws-sam-cli` |
| Git | Any | For cloning the repository |

**AWS account requirements:**
- Free-tier account with Bedrock access enabled in `us-east-1`
- IAM user or role with permissions: Lambda, API Gateway, SSM, IAM, CloudFormation, S3

**Google Cloud requirements:**
- Project with Google Calendar API enabled
- OAuth 2.0 client credentials (Client ID + Secret)
- Authorised redirect URI registered (added after first deploy)

---

## Step 1: Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-username/calendar-agent.git
cd calendar-agent

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install -r requirements.txt

# Install test dependencies
pip install pytest pytest-cov
```

---

## Step 2: Verify Python Package Structure

The project must be importable as a package from the workspace root:

```bash
# Verify the backend package is importable
python -c "from backend import config; print('Package OK')"
```

Expected output: `Package OK`

If this fails, ensure `backend/__init__.py` exists.

---

## Step 3: Configure Environment Variables (Local Development)

Create a `.env` file at the workspace root for local testing (never commit this file):

```bash
# .env — local development only
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
BEDROCK_REGION=us-east-1
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/callback
SSM_TOKEN_PATH=/calendar-agent/oauth
AWS_REGION=us-east-1
LOG_LEVEL=DEBUG
```

Add `.env` to `.gitignore`:

```bash
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
echo ".aws-sam/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

---

## Step 4: SAM Build (Lambda Package)

```bash
# Build the Lambda deployment package
sam build \
  --template-file infrastructure/template.yaml \
  --build-dir .aws-sam/build

# Expected output:
# Build Succeeded
# Built Artifacts  : .aws-sam/build
# Built Template   : .aws-sam/build/template.yaml
```

**Build artifacts produced:**
- `.aws-sam/build/CalendarAgentFunction/` — Lambda deployment package with all dependencies
- `.aws-sam/build/template.yaml` — processed CloudFormation template

---

## Step 5: Deploy to AWS

```bash
# Interactive deployment (prompts for all required parameters)
chmod +x infrastructure/deploy.sh
./infrastructure/deploy.sh
```

The script will:
1. Prompt for Google OAuth credentials and Bedrock model ID
2. Run `sam build`
3. Run `sam deploy` with `--resolve-s3` (creates an S3 bucket for artifacts automatically)
4. Output the API Gateway URL, OAuth callback URL, and Lambda ARN

**After first deploy:**
1. Copy the `OAuthCallbackUrl` output
2. Register it in Google Cloud Console → APIs & Services → Credentials → your OAuth 2.0 Client → Authorised redirect URIs
3. Re-deploy with the `FrontendUrl` parameter once the frontend S3 site is live

---

## Step 6: Deploy Frontend to S3

```bash
# Create an S3 bucket for the frontend (replace BUCKET_NAME with a unique name)
aws s3 mb s3://BUCKET_NAME --region us-east-1

# Enable static website hosting
aws s3 website s3://BUCKET_NAME \
  --index-document index.html \
  --error-document index.html

# Set public read policy
aws s3api put-bucket-policy \
  --bucket BUCKET_NAME \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::BUCKET_NAME/*"
    }]
  }'

# Update API_BASE_URL and GOOGLE_CLIENT_ID in frontend/app.js first, then upload
aws s3 sync frontend/ s3://BUCKET_NAME --delete
```

Frontend URL format: `http://BUCKET_NAME.s3-website-us-east-1.amazonaws.com`

---

## Verify Build Success

| Check | Command | Expected |
|-------|---------|----------|
| Python imports | `python -c "from backend.lambda_handler import handler"` | No errors |
| SAM build | `sam build --template-file infrastructure/template.yaml` | `Build Succeeded` |
| Stack deployed | `aws cloudformation describe-stacks --stack-name calendar-agent` | `StackStatus: CREATE_COMPLETE` |
| Health check | `curl https://<api-url>/Prod/health` | `{"status": "ok"}` |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`
- Ensure you are running commands from the workspace root (not from `backend/`)
- Ensure `backend/__init__.py` exists

### `SAM build fails — cannot find template`
- Run `sam build` from the workspace root, not from `infrastructure/`

### `Bedrock AccessDeniedException`
- Ensure Bedrock model access is enabled in the AWS console: Amazon Bedrock → Model access → Enable `Amazon Nova Lite`

### `Google OAuth redirect_uri_mismatch`
- The redirect URI in Google Cloud Console must exactly match `GOOGLE_REDIRECT_URI` in the Lambda environment variables
- After first deploy, copy the `OAuthCallbackUrl` output and register it in Google Cloud Console
