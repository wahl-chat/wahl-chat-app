# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Retire uploaded Wahlprogramme as soon as Abgeordnetenwatch publishes the same
programme. This is the COMMON direction: parties send us drafts before AW lists the
final document, so the upload is usually already in the corpus when AW arrives.

An ACCELERATOR, not a second policy. It deletes exactly what the manifesto_uploads
connector would retire on its own next run (see that connector's ``normalize()``),
and nothing else. The connector stays the backstop, which is why ``post_upsert``
swallows failures: a failure here costs latency, not correctness — the AW chunks are
already durably written, and raising would mark a succeeded item failed while the
runner's completion state already excludes it from the next discover().

Two rules, both learned from the coarse version this replaces:

  * Only ``wahlprogramm`` documents. The class comes from the object path, so a
    Grundsatzprogramm or Satzung — which AW never publishes — is never touched.
  * Deletes are addressed by each document's own deterministic ``source_item_id``,
    not by the party+region+date filter used to FIND them, so the blast radius is
    exactly the documents named in the log line.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

from qdrant_client import models

from ingestion.connectors.manifesto_uploads.mappers.corpus import UPLOAD_SOURCE
from ingestion.connectors.manifesto_uploads.storage_paths import (
    UploadPathError,
    parse_object_path,
)
from ingestion.ids import compute_source_item_id
from ingestion.schemas import ChunkRecord, SourceType

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


def _uploaded_twin_filter(
    party_id: str, region: str, publish_date: date_type
) -> models.Filter:
    """Find uploaded chunks for one party+region+election date (indexed fields only).

    A discovery filter, never a delete selector: it identifies a PROGRAMME, so what
    it returns still has to be split by document class before anything is removed.
    Matched as a single closed UTC day, not an open range, so a different election of
    the same party+region is never caught.
    """
    day_start = datetime.combine(publish_date, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(publish_date, time.max, tzinfo=timezone.utc)
    return models.Filter(
        must=[
            models.FieldCondition(
                key="source_type",
                match=models.MatchValue(value=SourceType.PARTY_MANIFESTO.value),
            ),
            models.FieldCondition(
                key="source", match=models.MatchValue(value=UPLOAD_SOURCE)
            ),
            models.FieldCondition(
                key="party_id", match=models.MatchValue(value=party_id)
            ),
            models.FieldCondition(key="region", match=models.MatchValue(value=region)),
            models.FieldCondition(
                key="publish_date",
                range=models.DatetimeRange(gte=day_start, lte=day_end),
            ),
        ]
    )


def _uploaded_object_paths(
    qdrant: "QdrantClient", collection_name: str, twin_filter: models.Filter
) -> list[str]:
    """Distinct object paths of the uploaded chunks matching *twin_filter*."""
    found: set[str] = set()
    next_offset = None
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=twin_filter,
            limit=1000,
            offset=next_offset,
            with_payload=["meta.storage_object_path"],
            with_vectors=False,
        )
        for point in points:
            path = ((point.payload or {}).get("meta") or {}).get("storage_object_path")
            if isinstance(path, str) and path:
                found.add(path)
        if next_offset is None:
            break
    return sorted(found)


def _delete_by_object_paths(
    qdrant: "QdrantClient", collection_name: str, object_paths: list[str]
) -> None:
    """Delete the uploaded chunks of exactly these documents.

    Addressed by the deterministic source_item_id the upload mapper derives from the
    object path (indexed uuid field), so this cannot reach a document not listed.
    """
    sids = [
        str(
            compute_source_item_id(
                SourceType.PARTY_MANIFESTO.value, path, source=UPLOAD_SOURCE
            )
        )
        for path in object_paths
    ]
    qdrant.delete(
        collection_name=collection_name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_item_id", match=models.MatchAny(any=sids)
                    ),
                    # Redundant by construction (the id is source-scoped) and kept
                    # anyway, so the selector is safe to read in isolation.
                    models.FieldCondition(
                        key="source", match=models.MatchValue(value=UPLOAD_SOURCE)
                    ),
                ]
            )
        ),
        wait=True,
    )


def supersede_uploaded_wahlprogramme(
    qdrant: "QdrantClient", collection_name: str, chunks: list[ChunkRecord]
) -> int:
    """Retire uploaded Wahlprogramme replaced by the just-upserted AW chunks.

    Called from post_upsert, i.e. only once the AW replacement is durably written, so
    the corpus never lacks the programme. Returns the number of uploaded DOCUMENTS
    retired.
    """
    # De-duplicate in case a future multi-party batch repeats the same triple.
    targets = {
        (c.party_id, c.region, c.publish_date)
        for c in chunks
        if c.source_type == SourceType.PARTY_MANIFESTO
    }

    retired = 0
    for party_id, region, publish_date in sorted(targets):
        twin_filter = _uploaded_twin_filter(party_id, region, publish_date)
        paths = _uploaded_object_paths(qdrant, collection_name, twin_filter)
        if not paths:
            continue

        superseded: list[str] = []
        kept: list[str] = []
        for path in paths:
            try:
                ref = parse_object_path(path)
            except UploadPathError:
                # Never guess a class for a path we cannot parse.
                kept.append(path)
                continue
            (superseded if ref.is_wahlprogramm else kept).append(path)

        if kept:
            logger.info(
                "keeping %d uploaded document(s) for party=%s region=%s election=%s "
                "that no Abgeordnetenwatch programme replaces: %s",
                len(kept),
                party_id,
                region,
                publish_date,
                ", ".join(kept),
            )
        if not superseded:
            continue

        _delete_by_object_paths(qdrant, collection_name, superseded)
        retired += len(superseded)
        # Loud on purpose — this removes an operator-uploaded document.
        logger.warning(
            "superseded %d uploaded Wahlprogramm(e) with the Abgeordnetenwatch copy: "
            "party=%s region=%s election_date=%s (%s). Drop the manifest line(s) so "
            "the uploads connector stops re-checking them.",
            len(superseded),
            party_id,
            region,
            publish_date,
            ", ".join(superseded),
        )
    return retired
