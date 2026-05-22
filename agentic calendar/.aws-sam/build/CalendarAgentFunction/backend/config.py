"""
config.py — Environment variable loading and application defaults.
All configuration is read from environment variables to support
easy deployment across environments without code changes.
"""

import os
from datetime import time


# ── Amazon Bedrock ────────────────────────────────────────────────────────────

BEDROCK_MODEL_ID: str = os.environ.get(
    "BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"
)
BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", "us-east-1")

# Maximum tokens the model may generate in a single response
BEDROCK_MAX_TOKENS: int = int(os.environ.get("BEDROCK_MAX_TOKENS", "1024"))

# ── Google OAuth 2.0 ──────────────────────────────────────────────────────────

GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI: str = os.environ.get("GOOGLE_REDIRECT_URI", "")

# Minimum Google Calendar API scopes required
GOOGLE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/calendar",
]

# ── AWS SSM / Secrets Manager ─────────────────────────────────────────────────

# Base path under which OAuth tokens are stored in SSM Parameter Store.
# Tokens are stored as:
#   {SSM_TOKEN_PATH}/access_token
#   {SSM_TOKEN_PATH}/refresh_token
#   {SSM_TOKEN_PATH}/expires_at
SSM_TOKEN_PATH: str = os.environ.get("SSM_TOKEN_PATH", "/calendar-agent/oauth")
AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")

# ── Session Defaults ──────────────────────────────────────────────────────────

# Default working hours (used when user has not configured their own)
DEFAULT_WORKING_HOURS_START: time = time(
    hour=int(os.environ.get("DEFAULT_WORKING_HOURS_START_HOUR", "9")),
    minute=0,
)
DEFAULT_WORKING_HOURS_END: time = time(
    hour=int(os.environ.get("DEFAULT_WORKING_HOURS_END_HOUR", "18")),
    minute=0,
)

# Default working days: 0=Monday … 4=Friday
DEFAULT_WORKING_DAYS: list[int] = [0, 1, 2, 3, 4]

# Default buffer between meetings in minutes
DEFAULT_BUFFER_MINUTES: int = int(os.environ.get("DEFAULT_BUFFER_MINUTES", "15"))

# Default confirmation mode: True = agent asks before every write/delete
DEFAULT_CONFIRMATION_MODE: bool = (
    os.environ.get("DEFAULT_CONFIRMATION_MODE", "true").lower() == "true"
)

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# ── Google Calendar API ───────────────────────────────────────────────────────

# Maximum number of events to fetch in a single list call
CALENDAR_MAX_RESULTS: int = int(os.environ.get("CALENDAR_MAX_RESULTS", "50"))

# Maximum retry attempts on Google Calendar API rate limit (HTTP 429)
CALENDAR_MAX_RETRIES: int = int(os.environ.get("CALENDAR_MAX_RETRIES", "3"))

# Base backoff delay in seconds (doubles on each retry)
CALENDAR_BACKOFF_BASE_SECONDS: float = float(
    os.environ.get("CALENDAR_BACKOFF_BASE_SECONDS", "1.0")
)
