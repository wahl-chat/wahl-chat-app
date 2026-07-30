# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Retire an uploaded manifesto once Abgeordnetenwatch publishes the same programme.

Matches on ``party_id`` + ``region`` + ``publish_date`` (all indexed already; both
sides stamp the ELECTION date, so agreement means "same programme"). If the dates
ever disagree the delete simply doesn't fire — a visible duplicate, never a
wrongly removed document.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING

from qdrant_client import models

from src.ingestion.connectors.manifesto_uploads.mappers.corpus import UPLOAD_SOURCE
from src.ingestion.schemas import ChunkRecord, SourceType

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


def _upload_twin_filter(
    party_id: str, region: str, publish_date: date_type
) -> models.Filter:
    """Filter selecting uploaded chunks for one party+region+election date.

    Matched as a single closed UTC day, not an open range, so a different election
    of the same party+region is never caught.
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


def supersede_uploaded_manifestos(
    qdrant: "QdrantClient", collection_name: str, chunks: list[ChunkRecord]
) -> int:
    """Delete uploaded manifesto chunks that the just-upserted AW chunks replace.

    Called from post_upsert, i.e. only after the replacement is durably written —
    the corpus never lacks the programme at any point in time. Returns the number
    of (party, region, date) groups whose uploaded twin was deleted.
    """
    # De-duplicate in case a future multi-party batch repeats the same triple.
    targets = {
        (c.party_id, c.region, c.publish_date)
        for c in chunks
        if c.source_type == SourceType.PARTY_MANIFESTO
    }

    superseded = 0
    for party_id, region, publish_date in sorted(targets):
        twin_filter = _upload_twin_filter(party_id, region, publish_date)
        existing = qdrant.count(
            collection_name=collection_name,
            count_filter=twin_filter,
            exact=True,
        ).count
        if not existing:
            continue
        qdrant.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=twin_filter),
            wait=True,
        )
        superseded += 1
        # Loud on purpose — this removes an operator-uploaded document.
        logger.warning(
            "superseded uploaded manifesto with the Abgeordnetenwatch copy: "
            "party=%s region=%s election_date=%s (%d chunk(s) deleted)",
            party_id,
            region,
            publish_date,
            existing,
        )
    return superseded
