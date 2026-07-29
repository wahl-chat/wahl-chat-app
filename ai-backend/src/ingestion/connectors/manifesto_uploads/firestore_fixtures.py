# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Live-Firestore backend for the election lookup (container / Cloud Run Job path).

The default backend reads the checked-in seed files, but those are not in the
container image: the Docker build context is ``ai-backend/`` and ``firebase/`` is
excluded from it. A scheduled Job therefore reads the running database instead —
where the live contexts are also the more accurate authority — selected explicitly
via ``ELECTION_FIXTURES_SOURCE=firestore``.

Validation is NOT duplicated here. This module only fetches, then hands the raw
document to ``election_fixtures.build_fixture``, so both backends enforce exactly
the same "no unreachable chunks" gate.

GDPR Art. 9 wall
----------------
Reads ``contexts/{id}`` and its ``parties`` subcollection ONLY — public election
configuration. It never touches ``users/`` (political opinions are special-category
data and must never reach corpus code) and never issues a ``collection_group``
query, which would fan out across every user's subcollections. Both prohibitions
are enforced for this tree by ``scripts/check_gdpr_wall.py`` in CI.

Client construction is deliberately independent of ``src.firebase_service``: that
module initialises the app and validates credentials at IMPORT time and can call
``sys.exit(1)``, which is acceptable for the API server but not for an ingestion
run that must fail as a normal, catchable per-item error.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING, cast

from src.ingestion.connectors.manifesto_uploads.election_fixtures import (
    ElectionFixture,
    FixtureLookupError,
    build_fixture,
)

if TYPE_CHECKING:
    from google.cloud.firestore import Client, DocumentSnapshot

logger = logging.getLogger(__name__)

_CONTEXTS = "contexts"
_PARTIES = "parties"


def _project_id() -> str | None:
    """Resolve the GCP project id the same way the app does."""
    return (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or os.getenv("FIREBASE_PROJECT_ID")
    )


@lru_cache(maxsize=1)
def _client() -> "Client":
    """Return a process-wide Firestore client.

    Uses Application Default Credentials, which in Cloud Run means the Job's
    service account with no key material to manage. With ``FIRESTORE_EMULATOR_HOST``
    set, anonymous credentials are used so a local run needs no real project.
    """
    from google.auth.credentials import AnonymousCredentials  # noqa: PLC0415
    from google.cloud.firestore import Client  # noqa: PLC0415

    project = _project_id()
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        return Client(
            project=project or "demo-wahl-chat",
            credentials=AnonymousCredentials(),  # type: ignore[no-untyped-call]
        )
    return Client(project=project) if project else Client()


def load_election_from_firestore(context_id: str) -> ElectionFixture:
    """Resolve one election from the live database.

    Args:
        context_id: Context doc id, e.g. ``"landtagswahl-sachsen-anhalt-2026"``.

    Returns:
        The populated ElectionFixture (validated by ``build_fixture``).

    Raises:
        FixtureLookupError: If the context doc is absent, unreadable, or missing a
            field the gate requires. A transport failure is wrapped rather than
            propagated raw so the runner records a per-item skip and leaves the
            already-stored chunks untouched, instead of the run dying mid-batch.
    """
    try:
        context_ref = _client().collection(_CONTEXTS).document(context_id)
        # The reference type is shared with the async client, so get() is typed as
        # "snapshot OR awaitable". This is the SYNC client, so it is always the
        # snapshot; awaiting would be a type error at runtime.
        snapshot = cast("DocumentSnapshot", context_ref.get())
    except Exception as exc:  # noqa: BLE001
        raise FixtureLookupError(
            f"could not read Firestore context {context_id!r}: {exc}"
        ) from exc

    if not snapshot.exists:
        raise FixtureLookupError(
            f"unknown election {context_id!r} — no contexts/{context_id} document. "
            "Seed the context (with region_path and level) before ingesting its PDFs"
        )

    try:
        party_ids = frozenset(
            doc.id for doc in context_ref.collection(_PARTIES).stream()
        )
    except Exception as exc:  # noqa: BLE001
        raise FixtureLookupError(
            f"could not read parties of Firestore context {context_id!r}: {exc}"
        ) from exc

    return build_fixture(
        context_id,
        snapshot.to_dict() or {},
        party_ids,
        origin=f"Firestore contexts/{context_id}",
    )
