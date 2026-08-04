# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure transforms: an uploaded manifesto PDF → party_manifesto ChunkRecord list.

No I/O — deterministic, unit-testable. Shares ``source_type="party_manifesto"``
with AW but carries ``source="upload"``, which keeps an upload's
``compute_source_item_id`` from ever colliding with an AW program id, and gives AW
a precise filter for superseding it later.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.ingestion.connectors.manifesto_uploads.election_fixtures import (
    ElectionFixture,
    require_party,
)
from src.ingestion.connectors.manifesto_uploads.storage_paths import UploadRef
from src.ingestion.ids import compute_source_item_id, make_chunk_key
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

# Connector discriminator written to ChunkRecord.source. Distinguishes an
# operator-uploaded manifesto from the AW-catalogue half of the same source_type.
UPLOAD_SOURCE = "upload"


class UploadManifestoMeta(BaseModel):
    """Typed builder for the uploaded-manifesto chunk ``meta`` dict (mirrors
    ManifestoMeta/VoteMeta/SpeechMeta): extra="forbid" catches typo'd keys;
    exclude_none drops null fields so no NULL keys reach Qdrant.
    """

    model_config = ConfigDict(extra="forbid")

    context_id: str
    storage_object_path: str
    document_name: str
    # Document's own date (filename); publish_date is the election date instead.
    document_date: str
    # "wahlprogramm" | "parteidokument" — from the object path's class folder.
    document_type: str
    election_level: Optional[str] = None
    total_pages: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    # Completed-parent marker, so a partially-committed multi-slice upsert is detectable.
    total_chunks: Optional[int] = None


def build_citation_title(ref: UploadRef, fixture: ElectionFixture) -> str:
    """Citation title: the document's own name plus the election it belongs to."""
    return f"{ref.title} – {fixture.name}"


def _content_hash(
    *,
    text: str,
    party_id: str,
    region: str,
    citation_url: str,
    citation_title: str,
    object_path: str,
    document_date: date_type,
    document_type: str,
    publish_date: date_type,
    page_start: Optional[int],
    page_end: Optional[int],
    total_pages: Optional[int],
) -> str:
    """Stable hash over text + every displayed/filtered field, so a corrected file
    or fixed document date re-embeds instead of being skipped as unchanged.
    """
    return hashlib.sha256(
        json.dumps(
            {
                "text": text,
                "party_id": party_id,
                "region": region,
                "citation_url": citation_url,
                "citation_title": citation_title,
                "object_path": object_path,
                "document_date": document_date.isoformat(),
                "document_type": document_type,
                "publish_date": publish_date.isoformat(),
                "page_start": page_start,
                "page_end": page_end,
                "total_pages": total_pages,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def build_upload_manifesto_records(
    ref: UploadRef,
    fixture: ElectionFixture,
    chunks: list[tuple[str, Optional[int], Optional[int]]],
    citation_url: str,
    total_pages: Optional[int] = None,
) -> list[ChunkRecord]:
    """Build the ChunkRecord list for one uploaded manifesto (pure, no I/O).

    Raises FixtureLookupError if the party isn't configured for this election.
    """
    party_id = require_party(fixture, ref.party_id)
    publish_date = fixture.election_date
    citation_title = build_citation_title(ref, fixture)

    # source-scoped so an upload and an AW program never share a source_item_id.
    sid = compute_source_item_id(
        SourceType.PARTY_MANIFESTO.value, ref.object_path, source=UPLOAD_SOURCE
    )

    total_chunks = len(chunks)
    records: list[ChunkRecord] = []
    for chunk_index, (text, page_start, page_end) in enumerate(chunks):
        # Never clobber an existing #fragment a manifest entry may already carry.
        chunk_citation_url = citation_url
        if page_start and "#" not in chunk_citation_url:
            chunk_citation_url = f"{chunk_citation_url}#page={page_start}"

        meta = UploadManifestoMeta(
            context_id=fixture.context_id,
            storage_object_path=ref.object_path,
            document_name=ref.document_name,
            document_date=ref.document_date.isoformat(),
            document_type=ref.document_type,
            election_level=fixture.level,
            total_pages=total_pages,
            page_start=page_start,
            page_end=page_end,
            total_chunks=total_chunks,
        ).model_dump(mode="json", exclude_none=True)

        records.append(
            ChunkRecord(
                chunk_key=make_chunk_key(sid, chunk_index),
                source_item_id=sid,
                chunk_index=chunk_index,
                text=text,
                party_id=party_id,
                region=fixture.region,
                authority_tier=AuthorityTier.SELF_REPORTED,
                source_type=SourceType.PARTY_MANIFESTO,
                publish_date=publish_date,
                citation_url=chunk_citation_url,
                citation_title=citation_title,
                source=UPLOAD_SOURCE,
                content_hash=_content_hash(
                    text=text,
                    party_id=party_id,
                    region=fixture.region,
                    citation_url=chunk_citation_url,
                    citation_title=citation_title,
                    object_path=ref.object_path,
                    document_date=ref.document_date,
                    document_type=ref.document_type,
                    publish_date=publish_date,
                    page_start=page_start,
                    page_end=page_end,
                    total_pages=total_pages,
                ),
                meta=meta or None,
            )
        )
    return records
