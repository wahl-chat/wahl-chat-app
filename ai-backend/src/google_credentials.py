# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Vertex AI service-account credentials — explicit, never process-wide ADC.

The service-account key belongs to the BILLING project (a different GCP project
than the one this service runs in). It must NEVER become ambient ADC:
``src/firebase_service.py`` falls back to a bare ``initialize_app()`` when no
cert file is on disk — which is always the case in the image, since
``.dockerignore`` keeps keys out of the build context. Exporting
``GOOGLE_APPLICATION_CREDENTIALS`` here would therefore make firebase-admin
authenticate as the WRONG project. These credentials are handed out only as an
explicit ``credentials=`` argument to the Gemini clients.

Cross-project IAM is not an option: the billing project enforces domain
restricted sharing (``iam.allowedPolicyMemberDomains``), so binding this
service's runtime identity there is rejected. A key minted inside the billing
project is the remaining path.

Nothing here raises. Absent or unusable credentials resolve to ``None`` so the
caller silently falls back to Google AI Studio (``GOOGLE_API_KEY``) — see
``src/llms.py`` and ``src/embeddings.py``.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Vertex AI requires the broad cloud-platform scope; there is no narrower one.
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# "global" matches the status quo: Google AI Studio, which served all Gemini
# traffic before this change, offers no regional pinning either — so this is not
# a data-residency regression. It is also the only location on the billing
# project where gemini-embedding-2 and the 2.5-lite / 3-preview chat models
# resolve; regional endpoints (europe-west3/4, us-central1) 404 on all of them
# and serve gemini-2.5-flash alone. Revisit if EU residency becomes a hard
# requirement — that would mean europe-west3 plus a much narrower model set.
_DEFAULT_LOCATION = "global"


@lru_cache(maxsize=1)
def get_vertex_credentials() -> Optional[Any]:
    """Return service-account credentials for Vertex AI, or None when unset.

    Reads ``VERTEX_SA_JSON`` (raw JSON, the Cloud Run / Secret Manager form)
    first, then ``VERTEX_SA_JSON_FILE`` (a path, the local-dev form).

    Cached: this is called from every Gemini construction site, and an uncached
    version would build a distinct credentials object per call, each with its
    own token cache and therefore its own token refresh.

    Tests that manipulate the VERTEX_* env vars must call
    ``get_vertex_credentials.cache_clear()``.

    Never raises — a missing or malformed key degrades to AI Studio rather than
    taking the process down at import time.
    """
    raw = os.getenv("VERTEX_SA_JSON")
    path = os.getenv("VERTEX_SA_JSON_FILE")

    try:
        from google.oauth2 import service_account  # noqa: PLC0415

        if raw and raw.strip():
            info = json.loads(raw)
            return service_account.Credentials.from_service_account_info(
                info, scopes=_SCOPES
            )
        if path and os.path.exists(path):
            return service_account.Credentials.from_service_account_file(
                path, scopes=_SCOPES
            )
    except Exception:  # noqa: BLE001 — any failure means "no Vertex", not "crash"
        logger.warning(
            "Vertex AI service-account credentials could not be loaded; "
            "falling back to Google AI Studio.",
            exc_info=True,
        )
        return None

    return None


def vertex_project() -> Optional[str]:
    """The billing project id.

    ``VERTEX_PROJECT_ID`` wins; otherwise it is read off the key itself. Note
    that ``GoogleGenerativeAIEmbeddings`` does NOT derive the project from the
    credentials the way the chat class does, so callers must pass the result of
    this function explicitly.
    """
    explicit = os.getenv("VERTEX_PROJECT_ID", "").strip()
    if explicit:
        return explicit
    credentials = get_vertex_credentials()
    return getattr(credentials, "project_id", None) if credentials else None


def vertex_location() -> str:
    """Vertex location. Defaults to "global" — see _DEFAULT_LOCATION.

    An empty or whitespace-only VERTEX_LOCATION falls back to the default rather
    than being passed through: a blank region would otherwise reach the client
    and fail obscurely, and `VERTEX_LOCATION=` is an easy thing to leave behind
    in a shell or a Cloud Run env spec.
    """
    return os.getenv("VERTEX_LOCATION", "").strip() or _DEFAULT_LOCATION


def vertex_enabled() -> bool:
    """True when Vertex is fully configured (credentials AND a project)."""
    return get_vertex_credentials() is not None and vertex_project() is not None
