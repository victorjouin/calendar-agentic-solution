"""
test_auth_manager.py — Unit tests for AuthManager.

All external dependencies (SSM, Google OAuth HTTP calls) are mocked.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.auth_manager import AuthManager, ReAuthRequiredException
from backend.models import OAuthTokens


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_tokens(expired: bool = False) -> OAuthTokens:
    if expired:
        expires_at = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    else:
        expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)
    return OAuthTokens(
        access_token="access-token-123",
        refresh_token="refresh-token-456",
        expires_at=expires_at,
    )


def _ssm_response(tokens: OAuthTokens) -> dict:
    return {
        "Parameter": {
            "Value": json.dumps(
                {
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_at": tokens.expires_at.isoformat(),
                }
            )
        }
    }


# ── exchange_code_for_tokens ──────────────────────────────────────────────────


class TestExchangeCodeForTokens:
    def test_success(self):
        auth = AuthManager()
        expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }

        with patch("requests.post", return_value=mock_response), \
             patch.object(auth, "store_tokens") as mock_store:
            tokens = auth.exchange_code_for_tokens("auth-code-abc")

        assert tokens.access_token == "new-access"
        assert tokens.refresh_token == "new-refresh"
        mock_store.assert_called_once()

    def test_failure_raises_value_error(self):
        auth = AuthManager()
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "invalid_grant"

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(ValueError, match="OAuth token exchange failed"):
                auth.exchange_code_for_tokens("bad-code")


# ── store_tokens / _load_tokens ───────────────────────────────────────────────


class TestStoreAndLoadTokens:
    def test_store_tokens_calls_ssm_put(self):
        auth = AuthManager()
        tokens = _make_tokens()

        with patch.object(auth, "_ssm") as mock_ssm:
            auth.store_tokens(tokens)

        mock_ssm.put_parameter.assert_called_once()
        call_kwargs = mock_ssm.put_parameter.call_args[1]
        assert call_kwargs["Type"] == "SecureString"
        assert call_kwargs["Overwrite"] is True

    def test_load_tokens_returns_none_when_not_found(self):
        from botocore.exceptions import ClientError

        auth = AuthManager()
        error_response = {"Error": {"Code": "ParameterNotFound", "Message": "not found"}}

        with patch.object(auth, "_ssm") as mock_ssm:
            mock_ssm.get_parameter.side_effect = ClientError(error_response, "GetParameter")
            result = auth._load_tokens()

        assert result is None

    def test_load_tokens_returns_tokens_when_found(self):
        auth = AuthManager()
        tokens = _make_tokens()

        with patch.object(auth, "_ssm") as mock_ssm:
            mock_ssm.get_parameter.return_value = _ssm_response(tokens)
            result = auth._load_tokens()

        assert result is not None
        assert result.access_token == tokens.access_token
        assert result.refresh_token == tokens.refresh_token


# ── get_valid_access_token ────────────────────────────────────────────────────


class TestGetValidAccessToken:
    def test_returns_token_when_valid(self):
        auth = AuthManager()
        tokens = _make_tokens(expired=False)

        with patch.object(auth, "_load_tokens", return_value=tokens):
            result = auth.get_valid_access_token()

        assert result == tokens.access_token

    def test_refreshes_when_expired(self):
        auth = AuthManager()
        expired_tokens = _make_tokens(expired=True)
        fresh_tokens = _make_tokens(expired=False)
        fresh_tokens.access_token = "refreshed-access"

        with patch.object(auth, "_load_tokens", return_value=expired_tokens), \
             patch.object(auth, "refresh_access_token", return_value=fresh_tokens) as mock_refresh:
            result = auth.get_valid_access_token()

        assert result == "refreshed-access"
        mock_refresh.assert_called_once_with(expired_tokens.refresh_token)

    def test_raises_reauth_when_no_tokens(self):
        auth = AuthManager()

        with patch.object(auth, "_load_tokens", return_value=None):
            with pytest.raises(ReAuthRequiredException):
                auth.get_valid_access_token()


# ── refresh_access_token ──────────────────────────────────────────────────────


class TestRefreshAccessToken:
    def test_success(self):
        auth = AuthManager()
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed-access",
            "expires_in": 3600,
        }

        with patch("requests.post", return_value=mock_response), \
             patch.object(auth, "store_tokens"):
            tokens = auth.refresh_access_token("my-refresh-token")

        assert tokens.access_token == "refreshed-access"
        # Refresh token should be preserved when Google doesn't return a new one
        assert tokens.refresh_token == "my-refresh-token"

    def test_raises_reauth_on_401(self):
        auth = AuthManager()
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(ReAuthRequiredException):
                auth.refresh_access_token("invalid-refresh-token")

    def test_raises_reauth_on_400(self):
        auth = AuthManager()
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(ReAuthRequiredException):
                auth.refresh_access_token("revoked-refresh-token")


# ── is_authenticated ──────────────────────────────────────────────────────────


class TestIsAuthenticated:
    def test_true_when_tokens_exist(self):
        auth = AuthManager()
        with patch.object(auth, "_load_tokens", return_value=_make_tokens()):
            assert auth.is_authenticated() is True

    def test_false_when_no_tokens(self):
        auth = AuthManager()
        with patch.object(auth, "_load_tokens", return_value=None):
            assert auth.is_authenticated() is False
