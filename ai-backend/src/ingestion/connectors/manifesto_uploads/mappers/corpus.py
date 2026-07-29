# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure transforms: an uploaded manifesto PDF → party_manifesto ChunkRecord list.

No I/O — deterministic and unit-testable. The connector supplies the parsed pages
and the resolved election fixture; everything here is arithmetic on those.

Shares ``source_type="party_manifesto"`` with the Abgeordnetenwatch connector but
carries ``source="upload"``, which:
  * folds into ``compute_source_item_id`` so an upload can never collide with an
    AW program id (both would otherwise hash a bare integer-ish external id);
  * gives the AW connector a precise filter for superseding an uploaded copy once
    the same programme appears upstream.

Page anchors are exact by construction: the pages are numbered by the parser that
read the very file the citation points at, so there is no printed-vs-physical
offset to correct (unlike plenary protocols, whose printed numbering is offset by
unnumbered front matter).
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
    """Typed builder for the uploaded-manifesto chunk ``meta`` dict.

    Mirrors the ManifestoMeta / VoteMeta / SpeechMeta convention: extra="forbid"
    rejects typo'd keys at build time, and None-valued fields are dropped by
    ``model_dump(exclude_none=True)`` so no NULL keys reach Qdrant.
    """

    model_config = ConfigDict(extra="forbid")

    context_id: str
    storage_object_path: str
    document_name: str
    # The document's OWN date (from the filename). publish_date on the envelope is
    # the election date instead, so both manifesto halves land in the same
    # retrieval window — this keeps the real date available for display and audit.
    document_date: str
    election_level: Optional[str] = None
    total_pages: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    # Completed-parent marker: how many chunks this document produced in total, so a
    # partially-committed multi-slice upsert is detectable rather than looking whole.
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
    publish_date: date_type,
    page_start: Optional[int],
    page_end: Optional[int],
    total_pages: Optional[int],
) -> str:
    """Stable hash over text + every displayed or filtered field.

    Covers provenance as well as prose so that re-uploading a corrected file, or
    fixing a document date, re-embeds instead of being skipped as unchanged by the
    runner's content-hash guard.
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

    Args:
        ref:          Parsed upload reference (election, party, name, document date).
        fixture:      Resolved election metadata (region, level, election date).
        chunks:       ``(text, page_start, page_end)`` tuples from ``chunk_pages``.
        citation_url: Public Storage URL of this document; each chunk appends its
                      own ``#page=`` anchor.
        total_pages:  Page count of the source PDF.

    Returns:
        One ChunkRecord per chunk.

    Raises:
        FixtureLookupError: If the party is not configured for this election.
    """
    party_id = require_party(fixture, ref.party_id)
    publish_date = fixture.election_date
    citation_title = build_citation_title(ref, fixture)

    # source-scoped so an uploaded document and an AW program can never share a
    # source_item_id even if their external ids coincide.
    sid = compute_source_item_id(
        SourceType.PARTY_MANIFESTO.value, ref.object_path, source=UPLOAD_SOURCE
    )

    total_chunks = len(chunks)
    records: list[ChunkRecord] = []
    for chunk_index, (text, page_start, page_end) in enumerate(chunks):
        # Deep-link to the page the passage starts on. Never clobber an existing
        # fragment (a manifest entry may already carry one).
        chunk_citation_url = citation_url
        if page_start and "#" not in chunk_citation_url:
            chunk_citation_url = f"{chunk_citation_url}#page={page_start}"

        meta = UploadManifestoMeta(
            context_id=fixture.context_id,
            storage_object_path=ref.object_path,
            document_name=ref.document_name,
            document_date=ref.document_date.isoformat(),
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
                    publish_date=publish_date,
                    page_start=page_start,
                    page_end=page_end,
                    total_pages=total_pages,
                ),
                meta=meta or None,
            )
        )
    return records
