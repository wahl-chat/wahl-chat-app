# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Pure corpus mapper for the openparliament_tv connector.

Turns ONE raw op session ``data[]`` item (JSON:API shape) into exactly ONE
whole-speech ``ChunkRecord`` (D-02): the timed sentence map, the video deep-link
payload, the shared cross-source ``speech_key``, and a change-aware
``content_hash``.

Structural analog: ``connectors/bundestag_speeches/mappers/corpus.py``. op keeps
the same ``ChunkRecord`` envelope but differs on:
  - ``authority_tier = FACTUAL_RECORD`` (DIP uses ``SELF_REPORTED``);
  - ``source = "op"`` (the D-11 discriminator; DIP writes ``"dip"``);
  - a video-timestamped ``citation_url`` (``videoFileURI#t={ts_start}``);
  - its OWN ``source_item_id`` derived from ``originMediaID`` — DISTINCT point IDs
    from DIP (coexist dedups on ``speech_key``, NOT shared point IDs — Q7);
  - a ``content_hash`` over text + sentence_map + video_uri + aligned + faction so
    a re-alignment / transcript correction re-writes the chunk (Q7).

Chunking reuses the DIP ``chunk_text`` VERBATIM (imported, not re-implemented) so
op and DIP share identical ≤6000-tok ``cl100k_base`` semantics (D-02). A normal
Bundestag speech is a single chunk.

Party resolution (D-10 / Q6):
  - ``faction.wid`` → the CORRECTED ``_OP_FACTION_SLUG_MAP`` slug;
  - an EMPTY ``faction.wid`` (minister / president) → MdB-Stammdaten by-name
    fallback → ``party_to_slug`` → else ``"unbekannt"`` (NEVER empty → a real party);
  - CSU refinement: when the faction slug is the joint ``"cdu"`` and the per-speaker
    MdB entry resolves to ``csu``, refine to ``csu`` (tenant parity with DIP / AW).

``external_id`` is intentionally left unset here — the connector's ``normalize()``
stamps ``YYYYMMDD(dateStart)`` via ``model_copy`` (mirroring DIP).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date as date_type
from typing import Optional

from src.ingestion.connectors.bundestag_speeches.mappers.corpus import (
    chunk_text,
    party_to_slug,
)
from src.ingestion.connectors.bundestag_speeches.mdb import mdb_party_for_speech
from src.ingestion.connectors.openparliament_tv.constants import _OP_FACTION_SLUG_MAP
from src.ingestion.connectors.openparliament_tv.parser import (
    _first_proceedings,
    _flatten_sentences,
    _main_speaker,
)
from src.ingestion.connectors.openparliament_tv.schemas import OpSpeechMeta
from src.ingestion.ids import compute_source_item_id, make_chunk_key
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType
from src.ingestion.speech_key import (
    agenda_slug_from_official,
    make_speech_key,
    slugify_speaker,
)

_corpus_logger = logging.getLogger(__name__)

# Connector discriminator stamped on every op chunk (D-11). Drives the
# source-scoped cursor (run.py::get_cursor) and the op supersede /
# DIP resurrection-guard filters, both keyed on speech_key + source.
_OP_SOURCE = "op"

# Data-source attribution label rendered by the app (Q8 / ODbL).
_OP_SOURCE_DATA = "openparliament.tv (ODbL)"

# Empty MdB lookup shape so subscript access in mdb.py never KeyErrors when the
# caller passes no lookup (or an empty dict, e.g. unit tests).
_EMPTY_MDB_LOOKUP: dict = {"by_id": {}, "by_name": {}}


def _normalize_mdb_lookup(mdb_lookup: Optional[dict]) -> dict:
    """Return a lookup that always exposes ``by_id`` / ``by_name`` keys."""
    if not mdb_lookup or "by_name" not in mdb_lookup or "by_id" not in mdb_lookup:
        return _EMPTY_MDB_LOOKUP
    return mdb_lookup


def _mdb_party_for_op_person(person: dict, mdb_lookup: dict) -> Optional[str]:
    """Resolve the speaker's party from MdB-Stammdaten via the by-name path.

    op's ``people[].wid`` is a Wikidata id, NOT the MdB numeric id, so the by-id
    path cannot match — we resolve by full name only. Reuses the DIP
    ``mdb_party_for_speech`` (by_name) by synthesising a speech-shaped dict.
    """
    lookup = _normalize_mdb_lookup(mdb_lookup)
    if lookup is _EMPTY_MDB_LOOKUP:
        return None

    firstname = person.get("firstname") or ""
    lastname = person.get("lastname") or ""
    name = f"{firstname} {lastname}".strip() or (person.get("label") or "")
    if not name:
        return None

    return mdb_party_for_speech({"speaker_xml_id": None, "speaker_name": name}, lookup)


def op_party_slug(person: dict, mdb_lookup: Optional[dict]) -> str:
    """Resolve a canonical party slug for an op main-speaker person dict (D-10/Q6).

    Order:
      1. non-empty ``faction.wid`` → ``_OP_FACTION_SLUG_MAP`` (CORRECTED map);
         unknown wid → ``"unbekannt"``;
         a joint ``"cdu"`` slug is refined to ``"csu"`` when the per-speaker MdB
         entry resolves to CSU;
      2. empty ``faction.wid`` (minister / president) → MdB by-name fallback →
         ``party_to_slug`` → else ``"unbekannt"``.

    An empty faction NEVER maps to a real party via the faction map — only via a
    genuine per-speaker MdB match.
    """
    faction = person.get("faction") or {}
    wid = (faction.get("wid") or "").strip()

    if wid:
        slug = _OP_FACTION_SLUG_MAP.get(wid, "unbekannt")
        # CSU refinement: joint Union label may hide an individual CSU member.
        if slug == "cdu":
            mdb_party = _mdb_party_for_op_person(person, mdb_lookup or {})
            if mdb_party is not None and party_to_slug(mdb_party) == "csu":
                return "csu"
        return slug

    # Empty faction → MdB fallback → unbekannt (never empty → a real party).
    mdb_party = _mdb_party_for_op_person(person, mdb_lookup or {})
    if mdb_party is not None:
        return party_to_slug(mdb_party)
    return "unbekannt"


def _iso_date(date_start: Optional[str]) -> str:
    """Return the ``YYYY-MM-DD`` prefix of an op ISO datetime (``dateStart``)."""
    return str(date_start or "")[:10]


def build_chunk_records(item: dict, mdb_lookup: Optional[dict] = None) -> list[ChunkRecord]:
    """Build ChunkRecord(s) for ONE raw op session ``data[]`` item.

    Applies the D-03 usability gate directly on the raw item: an unaligned item or
    one without a ``proceedings`` transcript yields ``[]`` (the connector treats an
    empty result as a skip). A usable item yields exactly one whole-speech chunk
    (or more only if the speech exceeds the shared ``chunk_text`` token budget).

    Args:
        item:       Raw op JSON:API speech item (keys: media, textContents, people,
                    agendaItem, electoralPeriod, session, dateStart, ...).
        mdb_lookup: MdB-Stammdaten lookup (``{by_id, by_name}``) for the empty-faction
                    / CSU fallback. Optional — an absent lookup degrades to ``unbekannt``.

    Returns:
        List of ChunkRecord (one per token chunk). ``[]`` for unusable items.
    """
    media = item.get("media") or {}

    # --- D-03 usability gate (mirrors parser.parse_session_json) ---
    if not media.get("aligned"):
        return []
    proceedings = _first_proceedings(item.get("textContents", []))
    if proceedings is None:
        return []

    origin_media_id = media.get("originMediaID")
    ext = str(origin_media_id) if origin_media_id is not None else ""

    whole_text, sentence_map = _flatten_sentences(proceedings, ext)
    if not whole_text.strip():
        return []

    # --- speaker / party ---
    person = _main_speaker(item.get("people", []))
    faction = person.get("faction") or {}
    faction_wid = faction.get("wid") or ""
    party_slug = op_party_slug(person, mdb_lookup)

    firstname = person.get("firstname")
    lastname = person.get("lastname")
    speaker_name = person.get("label") or " ".join(
        part for part in (firstname, lastname) if part
    )
    speaker_wid = person.get("wid")

    # --- session / agenda context ---
    electoral_period = item.get("electoralPeriod") or {}
    session_info = item.get("session") or {}
    ep = electoral_period.get("number")
    session_number = session_info.get("number")

    agenda = item.get("agendaItem") or {}
    agenda_title = agenda.get("title")
    agenda_official = agenda.get("officialTitle")
    agenda_type = agenda.get("type")

    date_start = item.get("dateStart")
    iso_date = _iso_date(date_start)

    # --- publish_date: strict ISO parse (no eval / strptime); skip on malformed ---
    try:
        publish_date = date_type.fromisoformat(iso_date)
    except (ValueError, TypeError):
        _corpus_logger.warning(
            "op build_chunk_records: speech %r has unparseable dateStart %r — skipping.",
            ext,
            date_start,
        )
        return []

    # --- shared cross-source speech_key (byte-parity with DIP via the shared helper) ---
    speaker_slug = slugify_speaker(firstname=firstname, lastname=lastname)
    agenda_slug = agenda_slug_from_official(agenda_official, agenda_type)
    speech_key: Optional[str]
    if ep is not None and session_number is not None:
        try:
            speech_key = make_speech_key(
                ep=int(ep),
                session=int(session_number),
                speaker_slug=speaker_slug,
                agenda_slug=agenda_slug,
            )
        except (TypeError, ValueError):
            speech_key = None
    else:
        speech_key = None

    # --- media deep-link payload ---
    video_uri = media.get("videoFileURI")
    audio_uri = media.get("audioFileURI")
    source_page = media.get("sourcePage")

    # --- citation: coarse video deep-link (second-pass locator refines later, D-02b) ---
    citation_title = f"{speaker_name}, {iso_date} (Video, {agenda_official})"
    # MED-01: only build the #t= deep-link when video_uri is truthy. The D-03 gate
    # checks aligned/proceedings, NOT videoFileURI, so video_uri may be None even
    # for an aligned item — an unguarded f-string would store the literal
    # "None#t=12.5" as the source url. Fall back to the source page instead.
    if video_uri and sentence_map:
        citation_url: Optional[str] = f"{video_uri}#t={sentence_map[0]['ts_start']}"
    else:
        citation_url = source_page or None

    # --- source-owned nested metadata ---
    meta = OpSpeechMeta(
        video_uri=video_uri,
        audio_uri=audio_uri,
        source_page=source_page,
        origin_media_id=ext or None,
        agenda_item_title=agenda_title,
        agenda_item_official=agenda_official,
        speaker_wid=speaker_wid,
        speaker_name=speaker_name or None,
        transcript_type="proceedings",
        aligned=True,
        sentence_map=sentence_map or None,
        creator=media.get("creator"),
        license=media.get("license"),
        source_data=_OP_SOURCE_DATA,
    ).model_dump(mode="json", exclude_none=True)

    # --- change-aware content_hash (Q7): re-alignment / correction re-writes the chunk ---
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "text": whole_text,
                "sentence_map": sentence_map,
                "video_uri": video_uri,
                "aligned": True,
                "faction_wid": faction_wid,
                # MED-02: include the RESOLVED party slug (indexed tenant field).
                # The empty-faction MdB-by-name fallback and the CSU refinement can
                # change party_id WITHOUT changing faction_wid; without this the
                # content-hash re-write guard (run.py) would keep the stale tenant.
                "party_slug": party_slug,
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    # --- deterministic op-OWN point identity (distinct from DIP) ---
    source_item_id = compute_source_item_id("parliamentary_speech", ext)

    wahlperiode: Optional[int] = int(ep) if ep is not None else None

    text_chunks = chunk_text(whole_text)

    records: list[ChunkRecord] = []
    for chunk_index, chunk_str in enumerate(text_chunks):
        chunk_key = make_chunk_key(source_item_id, chunk_index)
        records.append(
            ChunkRecord(
                chunk_key=chunk_key,
                source_item_id=source_item_id,
                chunk_index=chunk_index,
                text=chunk_str,
                party_id=party_slug,
                region="DE",
                authority_tier=AuthorityTier.FACTUAL_RECORD,
                source_type=SourceType.PARLIAMENTARY_SPEECH,
                publish_date=publish_date,
                citation_url=citation_url,
                citation_title=citation_title,
                # external_id intentionally NOT set — connector.normalize() stamps YYYYMMDD.
                wahlperiode=wahlperiode,
                speech_key=speech_key,
                source=_OP_SOURCE,
                content_hash=content_hash,
                meta=meta or None,
            )
        )

    return records
