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

Two failure modes, deliberately treated differently:

*Unconfigured* — no ``VERTEX_*`` credential source at all. The expected state in CI
and local development. Resolves to ``None`` quietly, and the caller falls back to
Google AI Studio (``GOOGLE_API_KEY``) — see ``src/llms.py`` and
``ai-backend/src/embeddings.py``.

*Misconfigured* — a source WAS supplied but is unusable (blank value, missing file,
corrupt key, unresolvable project). That is operator error, and staying quiet about
it is the worst outcome available: the service keeps answering while Gemini spend
keeps landing on the project this module exists to move it off. So it always logs a
warning, and under ``VERTEX_REQUIRED`` it raises ``VertexConfigError`` instead.

``VERTEX_REQUIRED`` is off by default: an import-time raise takes ``src/llms.py``
down and with it the whole service, which must not be the default for a key that is
optional. It is meant for deployed revisions, where a failed revision is strictly
better than invisible mis-billing.
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

_TRUTHY = ("1", "true", "yes")


class VertexConfigError(RuntimeError):
    """A Vertex credential source was supplied but is unusable, under strict mode.

    Only ever raised when ``VERTEX_REQUIRED`` is set. Absent that, the same
    conditions produce a warning and a fall back to Google AI Studio.
    """


def _vertex_required() -> bool:
    """Strict mode: escalate misconfiguration from a warning to a hard failure.

    Off by default so CI and local development keep the degrade-quietly contract.
    Set it on deployed revisions, where a revision that fails to start is easier
    to notice — and cheaper — than one that quietly bills the wrong project.

    Note that this escalates *broken* configuration only. With no credential
    source configured at all there is nothing to be strict about, and setting
    this alone must not take the service down.
    """
    return os.getenv("VERTEX_REQUIRED", "").strip().lower() in _TRUTHY


def _misconfigured(reason: str, *, exc_info: bool = False) -> None:
    """Report a supplied-but-unusable Vertex configuration. Never stays silent."""
    if _vertex_required():
        raise VertexConfigError(
            f"VERTEX_REQUIRED is set but Vertex AI is unusable: {reason}"
        )
    logger.warning(
        "Vertex AI disabled — %s Gemini traffic will bill Google AI Studio.",
        reason,
        exc_info=exc_info,
    )


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

    Returns None rather than raising when nothing is configured. When something
    IS configured and is broken, that is reported via ``_misconfigured`` — a
    warning by default, a ``VertexConfigError`` under ``VERTEX_REQUIRED``.
    """
    raw_env = os.getenv("VERTEX_SA_JSON")
    raw = (raw_env or "").strip()
    path = (os.getenv("VERTEX_SA_JSON_FILE") or "").strip()

    # Each supplied source is inspected BEFORE anything is loaded, and outside the
    # try below so these findings cannot be swallowed by its broad except. A
    # set-but-empty value and a path that does not exist are the two cases that
    # used to fall through both branches and return None with nothing logged.
    usable_raw = bool(raw)
    usable_path = bool(path) and os.path.exists(path)

    problems: list[str] = []
    if raw_env is not None and not raw:
        problems.append("VERTEX_SA_JSON is set but empty.")
    if path and not usable_path:
        problems.append(
            f"VERTEX_SA_JSON_FILE={path!r} does not exist (resolved to "
            f"{os.path.abspath(path)}); relative paths are read against the "
            "process working directory, not the repo root."
        )

    if not usable_raw and not usable_path:
        if problems:
            _misconfigured(" ".join(problems))
        else:
            logger.debug(
                "No Vertex AI credentials configured (VERTEX_SA_JSON / "
                "VERTEX_SA_JSON_FILE unset); using Google AI Studio."
            )
        return None

    # A broken source next to a working one — e.g. a leftover `VERTEX_SA_JSON=`
    # in .env while the file form is what is actually in use. Worth saying out
    # loud, but NOT worth escalating: strict mode asks "is Vertex unusable?", and
    # here it is usable, so raising would take the service down over a no-op.
    for problem in problems:
        logger.warning("Vertex AI configuration issue — %s", problem)

    try:
        from google.oauth2 import service_account  # noqa: PLC0415

        if usable_raw:
            info = json.loads(raw)
            return service_account.Credentials.from_service_account_info(
                info, scopes=_SCOPES
            )
        return service_account.Credentials.from_service_account_file(
            path, scopes=_SCOPES
        )
    except Exception as exc:  # noqa: BLE001 — degrade or escalate, never crash blindly
        _misconfigured(
            f"the supplied service-account key could not be loaded ({exc}).",
            exc_info=True,
        )
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
    """True when Vertex is fully configured (credentials AND a project).

    The single decision point for "is Vertex on" — ``src/llms.py`` and
    ``ai-backend/src/embeddings.py`` both route through here rather than re-deriving the
    two-part condition, so the semantics live in one place. Cheap to call: the
    credential lookup is cached and the project lookup is an env read.

    Also closes the last silent gap: credentials that load fine but yield no
    project id (a key without ``project_id``, ``VERTEX_PROJECT_ID`` unset) used
    to disable Vertex with nothing logged anywhere.
    """
    if get_vertex_credentials() is None:
        return False  # already reported by the resolver, quietly or otherwise
    if vertex_project() is None:
        _misconfigured(
            "a service-account key loaded but no project id could be resolved; "
            "set VERTEX_PROJECT_ID, or use a key that carries project_id."
        )
        return False
    return True
