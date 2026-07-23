# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Unit tests for optional Firebase auth gating of the premium-LLM flag.

A valid Firebase token does NOT prove a registered user — the frontend signs
every visitor in anonymously and that anonymous session yields a fully valid
token. Premium (user_is_logged_in) must therefore require an explicit
non-anonymous sign-in provider, not merely a verifiable token.
"""

from unittest.mock import patch

from src.auth import resolve_user_is_logged_in


class _Req:
    """Minimal stand-in for fastapi.Request (only .headers is read)."""

    def __init__(self, auth_header: str | None = None):
        self.headers = {"Authorization": auth_header} if auth_header else {}


def test_no_auth_header_is_not_premium():
    # No token at all → anonymous → not premium (no mock needed).
    assert resolve_user_is_logged_in(_Req(), "test") is False


def test_none_request_is_not_premium():
    # Non-HTTP caller (no request) → anonymous.
    assert resolve_user_is_logged_in(None, "test") is False


def test_no_valid_token_is_not_premium():
    with patch("src.auth.verify_optional_bearer_token", return_value=None):
        assert resolve_user_is_logged_in(_Req("Bearer x"), "test") is False


def test_anonymous_token_is_not_premium():
    anon = {"uid": "abc", "firebase": {"sign_in_provider": "anonymous"}}
    with patch("src.auth.verify_optional_bearer_token", return_value=anon):
        assert resolve_user_is_logged_in(_Req("Bearer anon"), "test") is False


def test_missing_firebase_block_is_not_premium():
    # Defensive: a token without a firebase sign-in block cannot be confirmed
    # as a real sign-in, so it must NOT unlock premium.
    with patch("src.auth.verify_optional_bearer_token", return_value={"uid": "abc"}):
        assert resolve_user_is_logged_in(_Req("Bearer x"), "test") is False


def test_real_provider_token_unlocks_premium():
    real = {"uid": "abc", "firebase": {"sign_in_provider": "password"}}
    with patch("src.auth.verify_optional_bearer_token", return_value=real):
        assert resolve_user_is_logged_in(_Req("Bearer real"), "test") is True
