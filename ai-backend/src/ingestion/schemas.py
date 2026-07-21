# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import uuid
from datetime import date as date_type
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================


class AuthorityTier(str, Enum):
    """Trustworthiness tier for a data source item."""

    AUTHORITATIVE = "authoritative"
    FACTUAL_RECORD = "factual_record"
    SELF_REPORTED = "self_reported"
    PROMOTIONAL = "promotional"


class SourceType(str, Enum):
    """Content category of the source item."""

    PARTY_MANIFESTO = "party_manifesto"
    VOTE_RECORD = "vote_record"
    DRUCKSACHE = "drucksache"
    QA_TRANSCRIPT = "qa_transcript"
    PARLIAMENTARY_SPEECH = "parliamentary_speech"  # Bundestag plenary speeches


class Stance(str, Enum):
    """A fraction's derived position on a vote (locked ``derive_stance`` output).

    ``NEUTRAL`` deliberately collapses two distinct cases (an exact top-two tie
    and an abstain-largest plurality) — see ``mappers.stance.derive_stance``.
    """

    AGREE = "agree"
    DISAGREE = "disagree"
    NEUTRAL = "neutral"
    ABSENT = "absent"


# =============================================================================
# Corpus models
# =============================================================================


class VoteResult(BaseModel):
    """One party's tally + derived stance on a single vote (vote_record payload).

    Stored as an element of ``ChunkRecord.vote_results`` — an array of objects
    (NOT a party-keyed dict) so Qdrant can nested-filter on ``party_id``/``stance``
    in the future.  ``stance`` is the locked rule output from
    ``mappers.stance.derive_stance``: agree | disagree | neutral | absent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    party_id: str = Field(..., description="Canonical party slug, e.g. 'spd'")
    stance: Stance = Field(..., description="Derived fraction position (derive_stance)")
    yes: int = Field(..., description="Count of 'yes' votes in the fraction")
    no: int = Field(..., description="Count of 'no' votes in the fraction")
    abstain: int = Field(..., description="Count of 'abstain' votes in the fraction")
    no_show: int = Field(..., description="Count of 'no_show' (did not vote) in the fraction")


class VoteMeta(BaseModel):
    """Source-owned nested metadata for vote_record chunks.

    Instantiated by corpus.py and dumped into ChunkRecord.meta via
    ``model_dump(mode="json", exclude_none=True)``.  Keeps vote-specific
    descriptive fields out of the shared envelope and off non-vote chunks.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vote_results: List[VoteResult] = Field(
        ...,
        description="Per-party tally + derived stance for the vote.",
    )
    motion_outcome: Optional[str] = Field(
        None,
        description=(
            "Overall result of the motion ('angenommen' | 'abgelehnt'), best-effort "
            "from the source's accepted flag; None when unavailable."
        ),
    )


class SpeechMeta(BaseModel):
    """Source-owned nested metadata for parliamentary_speech chunks.

    Dumped into ChunkRecord.meta via
    ``model_dump(mode="json", exclude_none=True)``.  Keeps speech-specific
    descriptive fields out of the shared envelope and off non-speech chunks.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    person_id: Optional[str] = Field(None, description="Speaker person identifier")
    speaker_name: Optional[str] = Field(None, description="Full name of the speaker")
    xml_rede_id: Optional[str] = Field(None, description="XML Rede ID from the protocol")
    protocol_id: Optional[str] = Field(None, description="Protocol identifier (e.g. '19/245')")
    protocol_api_id: Optional[str] = Field(None, description="API-level protocol identifier")


class ChunkRecord(BaseModel):
    """Payload stored alongside each Qdrant vector point.

    Design: shared ENVELOPE + source-owned nested ``meta`` object.
      - Indexed fields (tenant key, region, date, source type, etc.) stay top-level
        so Qdrant payload indexes remain effective.
      - Non-indexed source-specific descriptive fields move into ``meta``
        (a typed builder model dumped to dict at the connector boundary).
      - ``exclude_none=True`` on model_dump keeps absent envelope fields and
        None meta out of Qdrant — no NULL columns.

    Envelope fields (top-level, all sources):
        chunk_key, source_item_id, chunk_index, text, party_id, region,
        authority_tier, source_type, publish_date, citation_url, citation_title,
        external_id, party_ids, wahlperiode,
        speech_key, source, meta.

    vote_record meta (VoteMeta): vote_results, motion_outcome.
    parliamentary_speech meta (SpeechMeta): person_id, speaker_name,
        xml_rede_id, protocol_id, protocol_api_id.

    Note: the Qdrant point ID is computed externally via compute_chunk_id().
    This model carries NO region_path field — only the scalar region.
    Vote-record fields: party_ids (participating parties, filterable array; INDEXED top-level).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_key: str = Field(
        ...,
        description="Human-readable '{source_item_id}:{chunk_index:04d}' — PAYLOAD only, not the point ID",
    )
    source_item_id: uuid.UUID = Field(..., description="Parent source item UUID")
    chunk_index: int = Field(..., description="Zero-based chunk position within the item")
    text: str = Field(..., description="Chunk text content")
    party_id: str = Field(..., description="Short party slug, e.g. 'spd'")
    region: str = Field(..., description="Scalar region for MatchAny filter")
    authority_tier: AuthorityTier = Field(..., description="Trustworthiness tier")
    source_type: SourceType = Field(..., description="Content category")
    publish_date: date_type = Field(..., description="Date the source was published")
    citation_url: Optional[str] = Field(None, description="URL for SSE citation annotation")
    citation_title: Optional[str] = Field(None, description="Title for SSE citation annotation")
    # Cursor field:
    external_id: Optional[int] = Field(
        None,
        description=(
            "Monotonic integer source ID for the Qdrant cursor. "
            "Set to the raw AW poll integer for vote_record chunks; "
            "None for source types without a monotonic integer ID."
        ),
    )
    # Vote-record additions (INDEXED top-level — stays in envelope):
    party_ids: Optional[List[str]] = Field(
        None,
        description=(
            "Sorted list of canonical slugs of every party that participated in the "
            "vote — filterable via a non-tenant keyword array index. vote_record only."
        ),
    )
    # Shared legislative-period field (INDEXED top-level):
    wahlperiode: Optional[int] = Field(
        None,
        description=(
            "German legislative period (Wahlperiode) number, e.g. 19 for 19th Bundestag. "
            "Stamped by the connector at normalize() time."
        ),
    )
    # AW parliament_period ID for period-scoped retrieval.
    # Globally unique integer; does not collide across states (unlike wahlperiode int).
    legislature_period_id: Optional[int] = Field(
        None,
        description=(
            "AW parliament_period ID for the legislature this vote belongs to. "
            "Globally unique integer, e.g. 161 for 21st Bundestag (2025-), "
            "149 for Bayern 2023-2028. Used for period-scoped retrieval. "
            "None for older chunks that predate this field."
        ),
    )
    # Governance levels at which this vote is relevant. No Qdrant payload index —
    # the down-rank is post-fetch Python, not a Qdrant filter.
    relevance_levels: Optional[List[str]] = Field(
        None,
        description=(
            "Governance levels at which this vote is relevant. "
            "Values from {'federal', 'state', 'municipal'}. "
            "Set by AW connector normalize() from field_topics taxonomy lookup. "
            "None for non-vote chunks."
        ),
    )
    # Cross-source speech dedup + source discriminator (INDEXED top-level, keyword).
    # Written by BOTH the op and DIP speech connectors. `source_type` stays
    # `parliamentary_speech` for both — `source` is the discriminator axis.
    speech_key: Optional[str] = Field(
        None,
        description=(
            "Deterministic cross-source speech dedup identity "
            "`de-{ep}-{session}-{speaker_slug}-{agenda_slug}` (src/ingestion/speech_key.py). "
            "Written by BOTH the op and DIP connectors; the supersede-delete filter and the "
            "DIP pre-insert resurrection-guard key. INDEXED keyword. "
            "None on older chunks that predate this field."
        ),
    )
    source: Optional[str] = Field(
        None,
        description=(
            "Connector discriminator, values 'dip' | 'op'. Drives the source-scoped cursor "
            "(run.py::get_cursor) so op and DIP do not share a cursor. INDEXED keyword. "
            "None on older chunks that predate this field."
        ),
    )
    # Content hash for change-aware idempotent upserts. When a re-ingested item's
    # content_hash differs from the stored one, run.py re-embeds and re-writes the chunk
    # so upstream corrections (e.g. an AW vote tally fixed after first ingest) propagate;
    # unchanged items are skipped. None for connectors that do not compute it — those keep
    # plain point-id-existence idempotency.
    content_hash: Optional[str] = Field(
        None,
        description=(
            "Stable hash of the chunk's meaningful content (text + source-specific "
            "payload). Lets re-ingestion detect and apply upstream corrections. "
            "None when the connector does not compute it."
        ),
    )
    # Source-owned nested metadata (NOT indexed — descriptive fields only):
    meta: Optional[dict[str, Any]] = Field(
        None,
        description=(
            "Source-owned nested metadata. Connectors pass a typed builder "
            "(VoteMeta or SpeechMeta) dumped via model_dump(mode='json', exclude_none=True). "
            "Not indexed — do not filter on meta.* fields in Qdrant."
        ),
    )
