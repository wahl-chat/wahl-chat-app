# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure corpus mapper for the bundestag_speeches connector.

Exports:
    build_chunk_records(speech)  — produces list[ChunkRecord] from a speech dict
    chunk_text(text, ...)        — shared boundary-aware character splitter
                                   (re-exported from src.ingestion.chunking)
    party_to_slug(party)         — maps a raw party label to a canonical slug

Security notes:
    - Pydantic ChunkRecord validation (extra="forbid"): malformed fields are
      rejected at validation time, not silently dropped.
    - Empty-text speeches skipped (build_chunk_records returns [] for whitespace-
      only text).
    - publish_date: strict date.fromisoformat() with today() fallback — no
      arbitrary eval or strptime format strings.
    - Unknown party labels default to "unbekannt" rather than propagating a raw
      label into the corpus.

external_id handling:
    external_id is NOT set explicitly in build_chunk_records. The ChunkRecord
    default (None) is preserved so the caller (connector.normalize()) can stamp
    YYYYMMDD via model_copy(update={"external_id": ...}) without the mapper
    carrying protocol-date knowledge.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import date as date_type
from typing import Optional

from src.ingestion.chunking import chunk_text
from src.ingestion.ids import compute_source_item_id, make_chunk_key
from src.ingestion.party_slugs import (
    CANONICAL_PARTY_SLUGS,
    PARTY_SLUG_QUARANTINE,
    normalize_party_label,
)
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SpeechMeta, SourceType
from src.ingestion.speech_key import (
    agenda_slug_from_top_id,
    make_speech_key,
    slugify_speaker,
)

_corpus_logger = logging.getLogger(__name__)

# Connector discriminator stamped on every DIP chunk. Drives the
# source-scoped cursor (run.py::get_cursor) and the op supersede / DIP
# resurrection-guard filters, both keyed on speech_key + source.
_DIP_SOURCE = "dip"


def compute_speech_key(speech: dict) -> Optional[str]:
    """Compute the shared cross-source ``speech_key`` for a DIP speech dict.

    Uses the SAME ``src/ingestion/speech_key.py`` helper op uses so the two sources
    derive byte-identical keys for the same real speech:
      - ``ep``            = ``speech["wahlperiode"]``
      - ``session``       = ``speech["protocol_id"].split("/")[1]`` (dokumentnummer "20/101" → 101)
      - ``speaker_slug``  = ``slugify_speaker(full_name=speech["speaker_name"])``
      - ``agenda_slug``   = ``agenda_slug_from_top_id(speech["agenda_top_id"])``

    Graceful degradation: a missing / unparseable agenda yields an empty
    agenda component (no-agenda fallback) but still a valid key. When the
    wahlperiode or the session cannot be parsed, returns ``None`` rather than
    emitting a mismatched key that would silently break dedup / the supersede
    filter / the resurrection guard.

    Returns:
        The ``de-{ep}-{session}-{slug}-{agenda_slug}`` key, or ``None`` when ep /
        session are unparseable.
    """
    raw_wp = speech.get("wahlperiode")
    try:
        ep = int(raw_wp)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

    protocol_id = str(speech.get("protocol_id") or "")
    parts = protocol_id.split("/")
    if len(parts) < 2:
        return None
    try:
        session = int(parts[1].strip())
    except (TypeError, ValueError):
        return None

    return make_speech_key(
        ep=ep,
        session=session,
        speaker_slug=slugify_speaker(full_name=speech.get("speaker_name") or ""),
        agenda_slug=agenda_slug_from_top_id(speech.get("agenda_top_id")),
    )


# ---------------------------------------------------------------------------
# Party slug map — normalised case-insensitively on the stripped party string.
# Covers every distinct value produced by constants.PARTY_ALIASES:
#   SPD, CDU/CSU, BÜNDNIS 90/DIE GRÜNEN, FDP, AfD, DIE LINKE, BSW, fraktionslos
# Unknown/missing party values default to "unbekannt".
# ---------------------------------------------------------------------------

# Speeches only ever carry Bundestag fraction labels, so the map is the shared
# major-party core (incl. the CDU/CSU rule — see src/ingestion/party_slugs.py)
# plus an explicit DSU→quarantine: a non-fraction party appearing in a speech
# label should quarantine rather than mis-tenant.
_PARTY_SLUG_MAP: dict[str, str] = {
    **CANONICAL_PARTY_SLUGS,
    "dsu": PARTY_SLUG_QUARANTINE,
}


# Shared normaliser (soft-hyphen strip + whitespace collapse + lowercase).
_normalize_party_label = normalize_party_label


def party_to_slug(party: Optional[str]) -> str:
    """Map a raw party string from the speeches dict to a canonical slug.

    Matching is case-insensitive on the stripped string, with invisible
    formatting characters removed before lookup (U+00AD soft hyphen guard).
    Unknown or missing party strings map to "unbekannt".

    Covers every distinct value in constants.PARTY_ALIASES:
    SPD, CDU/CSU, BÜNDNIS 90/DIE GRÜNEN, FDP, AfD, DIE LINKE, BSW, fraktionslos.

    Args:
        party: Raw party string from the speech dict, or None.

    Returns:
        Canonical party slug (e.g. "spd", "fdp", "unbekannt").
    """
    if not party:
        return "unbekannt"
    clean = _normalize_party_label(party)
    if not clean:
        return "unbekannt"
    return _PARTY_SLUG_MAP.get(clean, "unbekannt")


# ---------------------------------------------------------------------------
# Chunking is centralised: chunk_text is imported from src.ingestion.chunking
# and re-exported here (the openparliament_tv mapper imports it from this
# module). Speeches use the shared boundary-aware character defaults.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Per-speech record builder (pure, no embeddings — unit-testable)
# ---------------------------------------------------------------------------


def build_chunk_records(speech: dict) -> list[ChunkRecord]:
    """Build ChunkRecord(s) for a single speech dict (no embeddings required).

    Skips speeches with empty or whitespace-only ``text``.

    Speech-specific descriptive fields (person_id, speaker_name, xml_rede_id,
    protocol_id, protocol_api_id) are packed into a SpeechMeta dict and stored
    in the envelope ``meta`` field. Top-level vote-specific fields are
    not set (defaults to None, excluded by exclude_none on upsert).

    ``external_id`` is NOT set explicitly here.
    The ChunkRecord field default (None) is preserved so the connector's
    normalize() can stamp YYYYMMDD via model_copy(update={"external_id": ...})
    without the mapper carrying protocol-date knowledge.

    Args:
        speech: Dict from the speeches JSONL with keys:
                id, text, date, party, speaker_name, protocol_id,
                pdf_url (optional), wahlperiode (optional),
                person_id (optional), xml_rede_id (optional),
                protocol_api_id (optional).

    Returns:
        List of ChunkRecord instances (one per token chunk). Empty list if
        the speech text is absent or whitespace-only.
    """
    text = speech.get("text") or ""
    if not text.strip():
        return []

    # Deterministic source_item_id from speech id string. source="dip" keeps the
    # id space disjoint from op's (op and DIP share source_type but draw ids from
    # different upstreams — see compute_source_item_id).
    speech_id = str(speech.get("id", ""))
    source_item_id = compute_source_item_id(
        "parliamentary_speech", speech_id, source="dip"
    )

    # Publish date — parse ISO YYYY-MM-DD; on error log a warning and return []
    # so the speech is skipped (consistent with the empty-text skip already in
    # this function, and with programs.py/qa.py policy). A date.today() fallback
    # would pollute the deterministic publish_date.
    raw_date = speech.get("date") or ""
    try:
        publish_date = date_type.fromisoformat(raw_date)
    except (ValueError, TypeError):
        _corpus_logger.warning(
            "build_chunk_records: speech %r has missing or unparseable date %r — skipping speech.",
            speech_id,
            raw_date,
        )
        print(
            f"WARNING: skipping speech {speech_id!r}: unparseable date {raw_date!r}",
            file=sys.stderr,
        )
        return []

    party_slug = party_to_slug(speech.get("party"))

    speaker_name = speech.get("speaker_name") or ""
    protocol_id = speech.get("protocol_id") or ""
    source_page = str(speech.get("source_page") or "") or None
    citation_title = f"{speaker_name}, {raw_date} (Protokoll {protocol_id}"
    citation_title += f", S. {source_page})" if source_page else ")"
    citation_url: Optional[str] = speech.get("pdf_url") or None
    # Deep-link into the protocol PDF when the parser could derive the PDF page
    # safely (start-seitennr present). Only appended to a fragment-free URL —
    # never clobber an existing anchor.
    pdf_page = speech.get("pdf_page")
    if citation_url and isinstance(pdf_page, int) and "#" not in citation_url:
        citation_url = f"{citation_url}#page={pdf_page}"

    # Wahlperiode — optional top-level indexed field. Tolerant coercion: bulk
    # JSONL rows can carry it as a string (or garbage) — degrade to None like
    # every other optional metadata field instead of aborting the speech.
    raw_wahlperiode = speech.get("wahlperiode")
    wahlperiode: Optional[int] = None
    if raw_wahlperiode is not None:
        try:
            wahlperiode = int(raw_wahlperiode)
        except (TypeError, ValueError):
            _corpus_logger.warning(
                "build_chunk_records: speech %r has non-integer wahlperiode %r — "
                "stamping None.",
                speech_id,
                raw_wahlperiode,
            )

    # Build source-owned SpeechMeta; omit None-valued fields.
    speech_meta_obj = SpeechMeta(
        person_id=speech.get("person_id") or None,
        speaker_name=speech.get("speaker_name") or None,
        xml_rede_id=speech.get("xml_rede_id") or None,
        protocol_id=speech.get("protocol_id") or None,
        protocol_api_id=speech.get("protocol_api_id") or None,
        source_page=source_page,
        page_quadrant=str(speech.get("page_quadrant") or "") or None,
    )
    meta_dict = speech_meta_obj.model_dump(mode="json", exclude_none=True)
    meta: Optional[dict] = meta_dict if meta_dict else None

    # Shared cross-source dedup identity + source discriminator.
    speech_key = compute_speech_key(speech)

    text_chunks = chunk_text(text)

    records: list[ChunkRecord] = []
    for chunk_index, chunk_str in enumerate(text_chunks):
        chunk_key = make_chunk_key(source_item_id, chunk_index)
        # Change-aware content_hash (mirrors the op mapper): PER-CHUNK text so an
        # upstream re-chunk or correction re-writes via run.py's guard; includes
        # the resolved party slug (indexed tenant field) so a slug fix re-writes
        # the stale tenant too, and the displayed citation (URL/title carry the
        # page coordinates) so a citation correction is refreshable rather than
        # permanently stale.
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "text": chunk_str,
                    "party_slug": party_slug,
                    "speech_key": speech_key,
                    "source": _DIP_SOURCE,
                    "protocol_id": protocol_id,
                    "citation_url": citation_url,
                    "citation_title": citation_title,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        records.append(
            ChunkRecord(
                chunk_key=chunk_key,
                source_item_id=source_item_id,
                chunk_index=chunk_index,
                text=chunk_str,
                party_id=party_slug,
                region="DE",
                # A plenary speech is a factual parliamentary record
                # regardless of transport — unified with the op mapper
                # (FACTUAL_RECORD) so the surviving tier no longer depends on
                # which connector won the dedup. Existing chunks keep the old
                # tier until re-ingest (tier is not part of content_hash).
                authority_tier=AuthorityTier.FACTUAL_RECORD,
                source_type=SourceType.PARLIAMENTARY_SPEECH,
                publish_date=publish_date,
                citation_url=citation_url,
                citation_title=citation_title,
                # NOTE: external_id intentionally NOT set here.
                # The connector's normalize() stamps YYYYMMDD via model_copy.
                # Legislative period — stamped when available in source.
                wahlperiode=wahlperiode,
                # Cross-source dedup identity + discriminator.
                speech_key=speech_key,
                source=_DIP_SOURCE,
                # Change-aware re-write guard (run.py).
                content_hash=content_hash,
                # Source-owned nested metadata.
                meta=meta,
            )
        )

    return records
