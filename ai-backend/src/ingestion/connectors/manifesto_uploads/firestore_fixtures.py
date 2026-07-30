# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Live-Firestore backend for the election lookup (container / Cloud Run Job path,
``ELECTION_FIXTURES_SOURCE=firestore`` — the seed files aren't in the image).

Only fetches; validation happens in ``election_fixtures.build_fixture``, shared
with the file backend.

GDPR Art. 9 wall: reads ``contexts/{id}`` + its ``parties`` subcollection ONLY —
never ``users/`` (special-category political-opinion data), never a
``collection_group`` query. Enforced by ``scripts/check_gdpr_wall.py`` in CI.

Client construction is independent of ``src.firebase_service``, which can
``sys.exit(1)`` on bad credentials — fine for the API server, not for an ingestion
run that must fail as a normal per-item error.
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
    """Return a process-wide Firestore client (ADC; anonymous creds when
    ``FIRESTORE_EMULATOR_HOST`` is set, so a local run needs no real project).
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
    """Resolve one election from the live database (validated by build_fixture).

    Wraps transport failures as FixtureLookupError so the runner records a
    per-item skip instead of the whole run dying mid-batch.
    """
    try:
        context_ref = _client().collection(_CONTEXTS).document(context_id)
        # Sync client: get() always returns a snapshot, never an awaitable.
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
