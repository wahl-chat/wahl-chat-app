# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""parse_session_json — op bulk session JSON → list of normalized speech dicts.

Role analog: bundestag_speeches/parser.parse_speeches_from_xml (raw source →
list-of-speech-dicts). Unlike the DIP parser this consumes JSON via the caller's
``json.loads`` (the OpTvClient already parsed it) — there is NO XML entity surface
here, so no XML hardening layer is imported.

Applies the alignment gate: a speech is only usable when
``media.aligned`` is truthy AND it has a ``proceedings`` transcript. Rather than
raise, each un-usable item is returned carrying a non-empty ``skip_reason`` marker
(mirroring the bundestag_speeches fetch→normalize skip_reason envelope); the
connector's normalize() converts that marker into a ValueError-skip.

For a usable item the parser flattens
``textContents[type=proceedings].textBody[speakerstatus=main-speaker].sentences[]``
into a timed ``sentence_map`` of ``{text, ts_start(float), ts_end(float)}``
and joins the main-speaker text into ``whole_text``. A malformed ``timeStart`` /
``timeEnd`` skips-and-warns that one sentence and never crashes the parse
(input-validation / DoS mitigation).

Public API:
  parse_session_json(session: dict) -> list[dict]
"""

from __future__ import annotations

import logging as _logging

_parser_logger = _logging.getLogger(__name__)


def _main_speaker(people: list) -> dict:
    """Return the first person with ``context == 'main-speaker'`` (else {})."""
    if not isinstance(people, list):
        return {}
    for person in people:
        if isinstance(person, dict) and person.get("context") == "main-speaker":
            return person
    return {}


def _first_proceedings(text_contents: list) -> dict | None:
    """Return the first ``type == 'proceedings'`` textContents block (else None)."""
    if not isinstance(text_contents, list):
        return None
    for block in text_contents:
        if isinstance(block, dict) and block.get("type") == "proceedings":
            return block
    return None


def _flatten_sentences(proceedings: dict, ext: str) -> tuple[str, list[dict]]:
    """Flatten main-speaker textBody into (whole_text, sentence_map).

    Drops president / interjection segments (speakerstatus != 'main-speaker').
    A malformed timeStart/timeEnd skips-and-warns that sentence (never crashes).
    """
    main_bodies = [
        tb
        for tb in proceedings.get("textBody", [])
        if isinstance(tb, dict) and tb.get("speakerstatus") == "main-speaker"
    ]

    whole_text = " ".join(str(tb.get("text", "")) for tb in main_bodies).strip()

    sentence_map: list[dict] = []
    for body in main_bodies:
        for sentence in body.get("sentences", []) or []:
            if not isinstance(sentence, dict):
                continue
            try:
                ts_start = float(sentence["timeStart"])
                ts_end = float(sentence["timeEnd"])
            except (KeyError, TypeError, ValueError):
                _parser_logger.warning(
                    "op parse (%s): dropping sentence with malformed timeStart/timeEnd: %r",
                    ext,
                    sentence.get("text", "")[:60],
                )
                continue
            sentence_map.append(
                {
                    "text": str(sentence.get("text", "")),
                    "ts_start": ts_start,
                    "ts_end": ts_end,
                }
            )

    return whole_text, sentence_map


def parse_session_json(session: dict) -> list[dict]:
    """Parse an op bulk session JSON dict into a list of normalized speech dicts.

    One dict per ``data[]`` item. Un-usable items (unaligned or ASR-only) carry a
    non-empty ``skip_reason`` and expose their id only under ``ext`` (never under
    ``origin_media_id``), so downstream consumers count exactly the usable speeches.
    Usable (aligned+proceedings) items carry ``origin_media_id``, ``whole_text``, a
    timed ``sentence_map``, and the raw fields the corpus mapper needs.

    Args:
        session: Parsed session JSON (JSON:API `{"meta": ..., "data": [...]}` shape).

    Returns:
        List of normalized speech dicts (usable + skipped).
    """
    speeches: list[dict] = []

    for item in session.get("data", []) or []:
        if not isinstance(item, dict):
            continue

        media = item.get("media") or {}
        origin_media_id = media.get("originMediaID")
        ext = str(origin_media_id) if origin_media_id is not None else ""

        electoral_period = item.get("electoralPeriod") or {}
        session_info = item.get("session") or {}
        ep = electoral_period.get("number")
        session_number = session_info.get("number")

        # --- alignment gate: unaligned → skippable (re-evaluate in the lookback window). ---
        if not media.get("aligned"):
            speeches.append(
                {
                    "ext": ext,
                    "skip_reason": f"{ext}: not aligned yet — re-evaluate later",
                    "ep": ep,
                    "session": session_number,
                }
            )
            continue

        # --- alignment gate: no proceedings transcript (ASR-only 'generated') → skippable. ---
        proceedings = _first_proceedings(item.get("textContents", []))
        if proceedings is None:
            speeches.append(
                {
                    "ext": ext,
                    "skip_reason": f"{ext}: no proceedings transcript",
                    "ep": ep,
                    "session": session_number,
                }
            )
            continue

        # --- usable: aligned + proceedings main-speaker text ---
        whole_text, sentence_map = _flatten_sentences(proceedings, ext)

        person = _main_speaker(item.get("people", []))
        faction = person.get("faction") or {}
        agenda = item.get("agendaItem") or {}

        speeches.append(
            {
                "ext": ext,
                "skip_reason": None,
                # identity the downstream helper/mapper keys on
                "origin_media_id": ext,
                # transcript
                "whole_text": whole_text,
                "sentence_map": sentence_map,
                "transcript_type": "proceedings",
                "aligned": True,
                # session context
                "parliament": item.get("parliament"),
                "ep": ep,
                "session": session_number,
                "date_start": item.get("dateStart"),
                # agenda
                "agenda_title": agenda.get("title"),
                "agenda_official": agenda.get("officialTitle"),
                "agenda_type": agenda.get("type"),
                # media deep-link payload (stored, NEVER fetched during ingest)
                "video_uri": media.get("videoFileURI"),
                "audio_uri": media.get("audioFileURI"),
                "source_page": media.get("sourcePage"),
                "creator": media.get("creator"),
                "license": media.get("license"),
                # speaker
                "faction_wid": faction.get("wid"),
                "speaker_wid": person.get("wid"),
                "firstname": person.get("firstname"),
                "lastname": person.get("lastname"),
                "speaker_label": person.get("label"),
            }
        )

    return speeches
