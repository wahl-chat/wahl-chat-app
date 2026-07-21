# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure corpus mapper for the bundestag_speeches connector.

Exports:
    build_chunk_records(speech)  — produces list[ChunkRecord] from a speech dict
    chunk_text(text, ...)        — splits text into token-bounded chunks
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
import re
import sys
from datetime import date as date_type
from typing import Optional

import tiktoken

from src.ingestion.ids import compute_source_item_id, make_chunk_key
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

# Invisible / zero-width formatting characters that may appear in party labels
# (e.g. soft hyphen U+00AD in "BÜNDNIS 90/DIE GRÜNEN" from the AW connector).
# Strip before lookup so the map key always matches cleanly.
_INVISIBLE_CHARS_RE = re.compile("[­​‌‍⁠﻿]")

_PARTY_SLUG_MAP: dict[str, str] = {
    # SPD
    "spd": "spd",
    # CDU/CSU family
    # Canonical rule (aligned with abgeordnetenwatch/connector.py::_AW_FRACTION_SLUG_MAP
    # and abgeordnetenwatch/mappers/corpus.py::_AW_FRACTION_SLUG_MAP):
    #   standalone CSU speech label → "csu" (DISTINCT tenant)
    #   joint "CDU/CSU" fraction label → "cdu" (Union fraction, not splittable from source)
    # Do NOT change "csu" back to "cdu" — that would mis-tenant CSU speeches
    # and break retrieval alignment with the AW connector and the csu manifesto tenant.
    "cdu/csu": "cdu",
    "cdu": "cdu",
    "csu": "csu",
    # Greens family
    "bündnis 90/die grünen": "gruene",
    "bündnis 90/die grüne": "gruene",
    "die grünen": "gruene",
    "grüne": "gruene",
    # FDP
    "fdp": "fdp",
    # AfD
    "afd": "afd",
    # DIE LINKE family
    "die linke": "linke",
    "die linke.": "linke",
    "linke": "linke",
    # BSW
    "bsw": "bsw",
    # fraktionslos
    "fraktionslos": "fraktionslos",
    # Explicit unknowns (DSU → unbekannt)
    "dsu": "unbekannt",
}


def _normalize_party_label(raw: str) -> str:
    """Normalise a party label for slug lookup.

    Strips invisible/zero-width formatting characters (notably U+00AD soft
    hyphen), collapses internal whitespace, strips, and lowercases.
    """
    clean = _INVISIBLE_CHARS_RE.sub("", raw)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip().lower()


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
# Token chunking
# ---------------------------------------------------------------------------

_ENC: Optional[tiktoken.Encoding] = None


def _get_encoding() -> tiktoken.Encoding:
    """Return (and cache) the cl100k_base tiktoken encoding."""
    global _ENC
    if _ENC is None:
        _ENC = tiktoken.get_encoding("cl100k_base")
    return _ENC


def chunk_text(
    text: str,
    max_tokens: int = 6000,
    overlap: int = 200,
) -> list[str]:
    """Split *text* into token-bounded chunks with a small overlap.

    Target ≤ max_tokens tokens per chunk (well under the 8191-token
    OpenAI embedding limit). Short texts that fit in a single chunk
    are returned as-is (list of one string).

    Args:
        text:       Full speech text to chunk.
        max_tokens: Maximum token count per chunk (default 6000).
        overlap:    Number of tokens to repeat at the start of the next
                    chunk for context continuity (default 200).

    Returns:
        List of string chunks. Empty-text input returns an empty list.
    """
    if not text or not text.strip():
        return []

    enc = _get_encoding()
    tokens = enc.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        if end == len(tokens):
            break
        start = end - overlap  # slide back by overlap for context continuity

    return chunks


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

    # Deterministic source_item_id from speech id string.
    speech_id = str(speech.get("id", ""))
    source_item_id = compute_source_item_id("parliamentary_speech", speech_id)

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
    citation_title = f"{speaker_name}, {raw_date} (Protokoll {protocol_id})"
    citation_url: Optional[str] = speech.get("pdf_url") or None

    # Wahlperiode — optional top-level indexed field.
    raw_wahlperiode = speech.get("wahlperiode")
    wahlperiode: Optional[int] = int(raw_wahlperiode) if raw_wahlperiode is not None else None

    # Build source-owned SpeechMeta; omit None-valued fields.
    speech_meta_obj = SpeechMeta(
        person_id=speech.get("person_id") or None,
        speaker_name=speech.get("speaker_name") or None,
        xml_rede_id=speech.get("xml_rede_id") or None,
        protocol_id=speech.get("protocol_id") or None,
        protocol_api_id=speech.get("protocol_api_id") or None,
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
        # the stale tenant too.
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "text": chunk_str,
                    "party_slug": party_slug,
                    "speech_key": speech_key,
                    "source": _DIP_SOURCE,
                    "protocol_id": protocol_id,
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
