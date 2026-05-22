"""
auth_manager.py — Google OAuth 2.0 lifecycle management.

Responsibilities:
- Exchange authorization code for access + refresh tokens
- Store tokens securely in AWS SSM Parameter Store (encrypted)
- Retrieve tokens and provide a valid access token (auto-refresh on expiry)
- Detect invalid/revoked refresh tokens and signal re-authentication need
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
import requests
from botocore.exceptions import ClientError

from backend import config
from backend.models import OAuthTokens

logger = logging.getLogger(__name__)


class ReAuthRequiredException(Exception):
    """Raised when the refresh token is invalid or revoked and the user must re-authenticate."""


class AuthManager:
    """Manages the Google OAuth 2.0 token lifecycle."""

    # Google OAuth token endpoint
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    # Google OAuth revocation endpoint (used to detect revoked tokens)
    _REVOKE_URL = "https://oauth2.googleapis.com/revoke"

    def __init__(self) -> None:
        self._ssm = boto3.client("ssm", region_name=config.AWS_REGION)

    # ── Public API ────────────────────────────────────────────────────────────

    def exchange_code_for_tokens(self, auth_code: str) -> OAuthTokens:
        """
        Exchange a Google OAuth authorization code for access and refresh tokens.
        Stores the resulting tokens in SSM Parameter Store.

        Args:
            auth_code: The authorization code received from the OAuth callback.

        Returns:
            OAuthTokens containing the access token, refresh token, and expiry.

        Raises:
            ValueError: If the token exchange fails.
        """
        logger.info("Exchanging OAuth authorization code for tokens")

        payload = {
            "code": auth_code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        response = requests.post(self._TOKEN_URL, data=payload, timeout=10)

        if not response.ok:
            logger.error("Token exchange failed: %s", response.text)
            raise ValueError(f"OAuth token exchange failed: {response.status_code}")

        data = response.json()
        tokens = self._parse_token_response(data)
        self.store_tokens(tokens)
        logger.info("OAuth tokens obtained and stored successfully")
        return tokens

    def store_tokens(self, tokens: OAuthTokens) -> None:
        """
        Persist OAuth tokens in AWS SSM Parameter Store (SecureString).

        Args:
            tokens: OAuthTokens to store.
        """
        token_data = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": tokens.expires_at.isoformat(),
        }

        self._ssm.put_parameter(
            Name=config.SSM_TOKEN_PATH,
            Value=json.dumps(token_data),
            Type="SecureString",
            Overwrite=True,
        )
        logger.debug("OAuth tokens stored in SSM at %s", config.SSM_TOKEN_PATH)

    def get_valid_access_token(self) -> str:
        """
        Retrieve a valid access token, refreshing it automatically if expired.

        Returns:
            A valid Google OAuth access token string.

        Raises:
            ReAuthRequiredException: If no tokens are stored or the refresh token is invalid.
        """
        tokens = self._load_tokens()
        if tokens is None:
            raise ReAuthRequiredException(
                "No OAuth tokens found. User must authenticate."
            )

        # Refresh if the access token has expired (with a 60-second buffer)
        now = datetime.now(tz=timezone.utc)
        if (tokens.expires_at - now).total_seconds() < 60:
            logger.info("Access token expired or expiring soon — refreshing")
            tokens = self.refresh_access_token(tokens.refresh_token)

        return tokens.access_token

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        """
        Use the stored refresh token to obtain a new access token from Google.

        Args:
            refresh_token: The Google OAuth refresh token.

        Returns:
            Updated OAuthTokens with a new access token and expiry.

        Raises:
            ReAuthRequiredException: If the refresh token is invalid or revoked.
        """
        logger.info("Refreshing OAuth access token")

        payload = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.post(self._TOKEN_URL, data=payload, timeout=10)

        if response.status_code in (400, 401):
            logger.warning("Refresh token invalid or revoked — re-auth required")
            raise ReAuthRequiredException(
                "Refresh token is invalid or revoked. User must re-authenticate."
            )

        if not response.ok:
            logger.error("Token refresh failed: %s", response.text)
            raise ValueError(f"OAuth token refresh failed: {response.status_code}")

        data = response.json()
        # Google does not return a new refresh token on refresh — keep the existing one
        if "refresh_token" not in data:
            data["refresh_token"] = refresh_token

        tokens = self._parse_token_response(data)
        self.store_tokens(tokens)
        logger.info("Access token refreshed and stored successfully")
        return tokens

    def is_authenticated(self) -> bool:
        """Return True if valid tokens exist in SSM."""
        return self._load_tokens() is not None

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _load_tokens(self) -> Optional[OAuthTokens]:
        """Load tokens from SSM Parameter Store. Returns None if not found."""
        try:
            response = self._ssm.get_parameter(
                Name=config.SSM_TOKEN_PATH, WithDecryption=True
            )
            data = json.loads(response["Parameter"]["Value"])
            return OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=datetime.fromisoformat(data["expires_at"]),
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ParameterNotFound":
                logger.info("No OAuth tokens found in SSM")
                return None
            raise

    @staticmethod
    def _parse_token_response(data: dict) -> OAuthTokens:
        """Parse a Google token endpoint response into an OAuthTokens object."""
        expires_in: int = data.get("expires_in", 3600)
        expires_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
        from datetime import timedelta
        expires_at = expires_at + timedelta(seconds=expires_in)

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
        )
