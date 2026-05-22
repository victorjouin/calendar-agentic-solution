#!/usr/bin/env bash
# destroy.sh — Tear down all Calendar-Agent AWS resources
#
# Usage:
#   chmod +x infrastructure/destroy.sh
#   ./infrastructure/destroy.sh

set -euo pipefail

STACK_NAME="sam-app"
REGION="${AWS_REGION:-eu-central-1}"

echo ""
echo "=========================================="
echo "  Calendar-Agent — DESTROY ALL RESOURCES"
echo "=========================================="
echo ""
echo "This will permanently delete:"
echo "  • Lambda function"
echo "  • API Gateway"
echo "  • IAM role"
echo "  • SSM parameter (OAuth tokens)"
echo "  • CloudWatch log group"
echo ""
read -rp "Are you sure? Type 'yes' to confirm: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "Deleting CloudFormation stack: ${STACK_NAME}..."
sam delete --stack-name "${STACK_NAME}" --region "${REGION}" --no-prompts

echo ""
echo "Removing SAM deployment bucket..."
SAM_BUCKET=$(aws cloudformation describe-stacks --stack-name aws-sam-cli-managed-default --region "${REGION}" --query "Stacks[0].Outputs[?OutputKey=='SourceBucket'].OutputValue" --output text 2>/dev/null || echo "")

if [ -n "$SAM_BUCKET" ]; then
  aws s3 rb "s3://${SAM_BUCKET}" --force
  aws cloudformation delete-stack --stack-name aws-sam-cli-managed-default --region "${REGION}"
  echo "SAM bucket deleted: ${SAM_BUCKET}"
else
  echo "SAM bucket not found or already deleted — skipping."
fi

echo ""
echo "=========================================="
echo "  All resources destroyed."
echo "=========================================="
echo ""
echo "Note: If you deployed a frontend S3 bucket separately,"
echo "delete it manually with:"
echo "  aws s3 rb s3://YOUR-FRONTEND-BUCKET --force"
echo ""
