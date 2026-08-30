# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Optional Firebase ID-token verification for backend routes.

The backend routes are reachable without authentication by design (anonymous
chat is a product requirement). Privileged request flags must never be trusted
from the request body alone: callers read an optional ``Authorization: Bearer
<Firebase ID token>`` header and verify it server-side.

Verification never rejects a request: an absent/invalid token simply resolves
to anonymous (no 401s). The web proxy routes forward the client's
``Authorization`` header verbatim; the client attaches its Firebase ID token
when signed in.
"""

import logging
from typing import Optional

from fastapi import Request
from firebase_admin import auth as firebase_auth

# Importing firebase_service guarantees firebase_admin.initialize_app() has run
# (including the emulator/anonymous-credential handling) before any
# verify_id_token call. verify_id_token itself honors
# FIREBASE_AUTH_EMULATOR_HOST for local/emulator runs.
import src.firebase_service  # noqa: F401

logger = logging.getLogger(__name__)


def verify_optional_bearer_token(request: Request) -> Optional[dict]:
    """Verify an optional ``Authorization: Bearer <Firebase ID token>`` header.

    Returns the decoded token claims when a valid token is present, else None.
    NEVER raises and NEVER rejects the request — anonymous access stays
    allowed. Callers must only honor privileged flags when this returns
    non-None.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer ") :].strip()
    if not token:
        return None
    try:
        return firebase_auth.verify_id_token(token)
    except Exception as err:  # noqa: BLE001 — any invalid token → anonymous
        logger.debug("Firebase ID token verification failed: %s", err)
        return None


def _has_real_signin(claims: dict) -> bool:
    """True only for a verified, NON-anonymous Firebase sign-in.

    A valid token is not proof of a registered user: the frontend signs every
    visitor in anonymously, and an anonymous session yields a fully valid
    Firebase ID token. The provider lives at
    ``claims["firebase"]["sign_in_provider"]`` ("anonymous" for anon sessions;
    "password"/"google.com"/… for real sign-ins). A real sign-in requires an
    explicit non-anonymous provider; anything else (anonymous, or an unexpected
    token shape) is denied.
    """
    firebase_claims = claims.get("firebase")
    if not isinstance(firebase_claims, dict):
        return False
    provider = firebase_claims.get("sign_in_provider")
    return bool(provider) and provider != "anonymous"


def resolve_user_is_logged_in(request: Optional[Request], route: str) -> bool:
    """Server-side truth for whether the caller has a real (non-anonymous) sign-in.

    Derived SOLELY from the request's Firebase token — never from a
    client-supplied flag. Returns True only when the request carries a valid,
    NON-anonymous Firebase ID token (every visitor is signed in anonymously, so
    an anonymous token — though valid — must not count as a real user). A missing
    request (non-HTTP callers) is treated as anonymous.
    """
    if request is None:
        return False
    claims = verify_optional_bearer_token(request)
    if claims is None:
        logger.debug("%s: no valid Firebase ID token — not signed in.", route)
        return False
    if not _has_real_signin(claims):
        logger.debug(
            "%s: token is anonymous / lacks a real sign-in provider.",
            route,
        )
        return False
    return True
