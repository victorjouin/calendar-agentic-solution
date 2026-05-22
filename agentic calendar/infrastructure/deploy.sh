#!/usr/bin/env bash
# deploy.sh — Build and deploy Calendar-Agent to AWS using AWS SAM
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - AWS SAM CLI installed (pip install aws-sam-cli)
#   - Python 3.11 available
#   - An S3 bucket for SAM deployment artifacts (created automatically on first run)
#
# Usage:
#   chmod +x infrastructure/deploy.sh
#   ./infrastructure/deploy.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

STACK_NAME="calendar-agent"
REGION="${AWS_REGION:-us-east-1}"
# SAM uses an S3 bucket to store deployment artifacts.
# The bucket is created automatically by sam deploy --resolve-s3.
SAM_CONFIG_FILE="infrastructure/samconfig.toml"

# ── Prompt for required parameters ───────────────────────────────────────────

echo ""
echo "=========================================="
echo "  Calendar-Agent — AWS SAM Deployment"
echo "=========================================="
echo ""

read -rp "Google OAuth Client ID: " GOOGLE_CLIENT_ID
read -rsp "Google OAuth Client Secret: " GOOGLE_CLIENT_SECRET
echo ""
read -rp "Google OAuth Redirect URI (e.g. https://<api-id>.execute-api.${REGION}.amazonaws.com/Prod/oauth/callback): " GOOGLE_REDIRECT_URI
read -rp "Frontend URL (S3 website URL, or leave blank if not yet deployed): " FRONTEND_URL
read -rp "Bedrock Model ID [amazon.nova-lite-v1:0]: " BEDROCK_MODEL_ID
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-amazon.nova-lite-v1:0}"

echo ""
echo "Building Lambda package..."
echo ""

# ── SAM Build ─────────────────────────────────────────────────────────────────

sam build \
  --template-file infrastructure/template.yaml \
  --build-dir .aws-sam/build

echo ""
echo "Deploying to AWS (region: ${REGION}, stack: ${STACK_NAME})..."
echo ""

# ── SAM Deploy ────────────────────────────────────────────────────────────────

sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --resolve-s3 \
  --parameter-overrides \
    "GoogleClientId=${GOOGLE_CLIENT_ID}" \
    "GoogleClientSecret=${GOOGLE_CLIENT_SECRET}" \
    "GoogleRedirectUri=${GOOGLE_REDIRECT_URI}" \
    "FrontendUrl=${FRONTEND_URL}" \
    "BedrockModelId=${BEDROCK_MODEL_ID}" \
    "BedrockRegion=${REGION}" \
  --no-fail-on-empty-changeset

echo ""
echo "=========================================="
echo "  Deployment complete!"
echo "=========================================="
echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
  --output table

echo ""
echo "Next steps:"
echo "  1. Copy the OAuthCallbackUrl above and register it in Google Cloud Console"
echo "     (APIs & Services > Credentials > your OAuth 2.0 Client > Authorised redirect URIs)"
echo "  2. Copy the ApiBaseUrl and update frontend/app.js (API_BASE_URL constant)"
echo "  3. Deploy the frontend to S3 (see frontend/README.md)"
echo "  4. Update the stack with the FrontendUrl once the S3 website is live:"
echo "     sam deploy ... --parameter-overrides FrontendUrl=<your-s3-url>"
echo ""
