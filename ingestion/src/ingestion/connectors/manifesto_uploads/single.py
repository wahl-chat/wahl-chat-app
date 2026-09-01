# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Event-scoped single-document runs — the Firebase storage-trigger entrypoints.

``firebase/ingest_functions/main.py`` calls these with one object path per
storage event (finalize → ``ingest_one``, delete → ``retire_one``). Everything
of substance — AW-overlap retirement, content-hash skip, orphan cleanup,
footprint retire, embed backoff, fingerprint guard — is the ordinary connector
driven through the ordinary ``run_connector``; the only change is that
``discover()`` returns the event's path instead of a bucket/manifest work-list.

The daily ``ingest-manifesto-uploads`` reconcile job remains the correctness
backstop for dropped or failed events: both paths run the same code, so their
writes are byte-identical and idempotent against each other.
"""

from __future__ import annotations

import os
from typing import Optional

from ingestion.connectors.manifesto_uploads.connector import (
    ManifestoUploadsConnector,
)

_TASK_TYPE = "RETRIEVAL_DOCUMENT"  # corpus-write side; must match run.py


class _SingleUploadConnector(ManifestoUploadsConnector):
    """A connector whose work-list is exactly one object path.

    ``expected=True`` offers the document for ingestion (fetch/normalize run in
    full, including the AW-overlap retirement); ``expected=False`` declares it
    should no longer exist, which fetch() flags as retired and the runner turns
    into a footprint delete — the delete-event path.
    """

    def __init__(
        self, object_path: str, *, expected: bool, env: Optional[str] = None
    ) -> None:
        super().__init__(env=env)
        self._single_path = object_path
        self._single_expected = expected

    def discover(self, since: Optional[int]) -> list[str]:
        # The election-date floor keeps the same semantics as a full run: a
        # below-floor document is neither ingested nor retired ("not now", not
        # "should not exist"), so the event becomes a no-op.
        if not self._in_scope(self._single_path):
            self._expected_paths = set()
            self._discovered = True
            return []
        self._expected_paths = (
            {self._single_path} if self._single_expected else set()
        )
        self._discovered = True
        return [self._single_path]


def _default_clients():  # noqa: ANN202 — (QdrantClient, Embeddings), built lazily
    # Mirrors run.py's __main__ client wiring (URL/key/timeout envs, document
    # task type). Imported lazily so the trigger's cheap skip paths never build
    # an embeddings client.
    from qdrant_client import QdrantClient  # noqa: PLC0415
    from wahlchat_common.embeddings import get_embeddings  # noqa: PLC0415

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=int(os.getenv("QDRANT_TIMEOUT", "120")),
    )
    return qdrant, get_embeddings(task_type=_TASK_TYPE)


def _run(
    object_path: str,
    *,
    expected: bool,
    env: Optional[str],
    qdrant,  # noqa: ANN001 — injectable for tests
    embed,  # noqa: ANN001
    collection_name: Optional[str],
):  # noqa: ANN202 — RunReport
    from ingestion.run import run_connector  # noqa: PLC0415
    from ingestion.setup_collection import COLLECTION_NAME  # noqa: PLC0415

    if qdrant is None or embed is None:
        default_qdrant, default_embed = _default_clients()
        qdrant = qdrant if qdrant is not None else default_qdrant
        embed = embed if embed is not None else default_embed

    connector = _SingleUploadConnector(object_path, expected=expected, env=env)
    return run_connector(
        connector, qdrant, embed, collection_name or COLLECTION_NAME
    )


def ingest_one(
    object_path: str,
    *,
    env: Optional[str] = None,
    qdrant=None,  # noqa: ANN001
    embed=None,  # noqa: ANN001
    collection_name: Optional[str] = None,
):  # noqa: ANN201 — RunReport
    """Ingest exactly one uploaded PDF (storage finalize event)."""
    return _run(
        object_path,
        expected=True,
        env=env,
        qdrant=qdrant,
        embed=embed,
        collection_name=collection_name,
    )


def retire_one(
    object_path: str,
    *,
    env: Optional[str] = None,
    qdrant=None,  # noqa: ANN001
    embed=None,  # noqa: ANN001
    collection_name: Optional[str] = None,
):  # noqa: ANN201 — RunReport
    """Retire exactly one deleted PDF's stored footprint (storage delete event)."""
    return _run(
        object_path,
        expected=False,
        env=env,
        qdrant=qdrant,
        embed=embed,
        collection_name=collection_name,
    )
