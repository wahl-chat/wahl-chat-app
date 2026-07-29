# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Retire an uploaded manifesto once Abgeordnetenwatch publishes the same programme.

Uploaded PDFs exist because AW's catalogue does not cover an election yet. AW does
open a period before election day (they carry the 2026 Baden-Württemberg and
Rheinland-Pfalz programmes already), so a document ingested from an upload is
expected to be superseded by its AW twin later. When that happens the AW copy wins:
it is the citable public source, and keeping both would let one answer cite the
same programme twice.

Match rule — deliberately narrow
--------------------------------
An uploaded chunk is superseded only when the AW programme agrees on all three of
``party_id``, ``region`` and ``publish_date``. All three are indexed already, so no
new payload field and no corpus re-ingest is needed.

``publish_date`` is the tie-breaker that makes this safe: both halves stamp it as
the ELECTION date (AW from its parliament-period, uploads from the context doc), so
agreement means "same party, same region, same election". If the two dates ever
disagree the delete simply does not fire — the failure mode is a visible duplicate,
never a wrongly removed document, which is the right way round for a destructive
step driven by a fuzzy identity.
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

    The date is matched as a single closed UTC day rather than an open range, so a
    programme for a DIFFERENT election of the same party and region is never caught.
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

    Called from the AW manifesto connector's ``post_upsert``, i.e. only after the
    replacement is durably written — the corpus never lacks the programme at any
    point in time.

    Args:
        qdrant:          Initialised QdrantClient.
        collection_name: Collection the AW chunks were written to.
        chunks:          The AW ChunkRecords just upserted (one programme).

    Returns:
        Number of (party, region, election-date) groups whose uploaded twin was
        deleted. Zero when nothing matched, which is the normal case.
    """
    # One programme's chunks all share these three values; de-duplicate anyway so a
    # future multi-party batch cannot issue the same delete repeatedly.
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
        # Logged loudly: this removes a document an operator uploaded by hand, so
        # the replacement must be visible in the run output, not inferred.
        logger.warning(
            "superseded uploaded manifesto with the Abgeordnetenwatch copy: "
            "party=%s region=%s election_date=%s (%d chunk(s) deleted)",
            party_id,
            region,
            publish_date,
            existing,
        )
    return superseded
