# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Speech order, page anchors and cross-source twins from the protocol XML.

The corpus knows neither the order of the speeches in a debate (a scroll
returns points by id, and op.tv speeches carry no time of day) nor, for
openparliament.tv records, the protocol page: their DIP twin was merged away at
ingest. The protocol XML next to the PDF lists every speech in the order it was
given, with its PDF page.

Speeches are matched to it by speaker and agenda item. Where the two sources
file a debate under different items (a joint debate the protocol keeps under
"Tagesordnungspunkt 24" and openparliament.tv under "Zusatzpunkt 19"), the
speaker is looked up in the protocol block that holds most of the item's
speakers. Two corpus speeches matched to the same protocol speech are one
speech from both sources; the openparliament.tv one is kept, as everywhere.

Everything that reads "the first speech" depends on that order: the Fraktion
that opened the debate, the opening quote, the citations, the video. So a
debate whose protocol cannot be read is not built at all, rather than built in
an arbitrary order; the next run tries again.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Optional

import defusedxml.ElementTree as ElementTree

from ingestion.connectors.bundestag_speeches.client import fetch_text
from ingestion.connectors.bundestag_speeches.parser import parse_speeches_from_xml
from ingestion.feed.reader import AgendaItem, SittingDay, Speech
from ingestion.speech_key import agenda_slug_from_top_id, slugify_speaker

logger = logging.getLogger(__name__)

# Bundestag protocol PDFs live at dserver.bundestag.de/btp/{wp}/{wp}{nnn}.pdf
# with the XML beside them; nothing else is rewritten into an XML URL.
_PROTOCOL_PDF_RE = re.compile(r"^https://dserver\.bundestag\.de/btp/\d+/\d+\.pdf$")
_PROTOCOL_ID_RE = re.compile(r"^(\d+)/(\d+)$")
# de-{ep}-{session}-{speaker}-{agenda}; the agenda part may be empty.
_KEY_SPEAKER_RE = re.compile(r"^de-\d+-\d+-(.*)-(?:(?:top|zp)\d+)?$")

FetchText = Callable[[str], str]


@dataclass(frozen=True)
class ProtocolSpeech:
    position: int
    # 1-based page in the PDF; None when the table of contents has no entry.
    page: Optional[int]
    speaker: str
    agenda: str


@dataclass
class ProtocolIndex:
    speeches: list[ProtocolSpeech] = field(default_factory=list)
    session_date: Optional[date] = None


def protocol_xml_url(pdf_url: str) -> Optional[str]:
    base = pdf_url.split("#", 1)[0]
    if not _PROTOCOL_PDF_RE.match(base):
        return None
    return base[: -len(".pdf")] + ".xml"


def _session_date(xml_text: str) -> Optional[date]:
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        return None
    raw = root.get("sitzung-datum")
    try:
        return datetime.strptime(raw, "%d.%m.%Y").date() if raw else None
    except ValueError:
        return None


def protocol_index(xml_text: str) -> ProtocolIndex:
    index = ProtocolIndex(session_date=_session_date(xml_text))
    for position, speech in enumerate(parse_speeches_from_xml(xml_text)):
        page = speech.get("pdf_page")
        index.speeches.append(
            ProtocolSpeech(
                position=position,
                page=page if isinstance(page, int) else None,
                speaker=slugify_speaker(full_name=speech.get("speaker_name") or ""),
                agenda=agenda_slug_from_top_id(speech.get("agenda_top_id")),
            )
        )
    return index


def speaker_slug(speech: Speech) -> str:
    """The speaker part of the speech_key, or the name slugged the same way
    when the key has none."""
    match = _KEY_SPEAKER_RE.match(speech.speech_key or "")
    if match and match.group(1):
        return match.group(1)
    return slugify_speaker(full_name=speech.speaker or "")


def _match_item(item: AgendaItem, index: ProtocolIndex) -> dict[str, ProtocolSpeech]:
    """source_item_id -> the protocol speech it is. A speaker who takes the
    floor twice under one item takes their places in order."""
    taken: set[int] = set()
    matched: dict[str, ProtocolSpeech] = {}

    def take(speech: Speech, agenda: str) -> bool:
        speaker = speaker_slug(speech)
        found = next(
            (
                p
                for p in index.speeches
                if p.speaker == speaker
                and p.agenda == agenda
                and p.position not in taken
            ),
            None,
        )
        if found is None:
            return False
        taken.add(found.position)
        matched[speech.source_item_id] = found
        return True

    unmatched = [s for s in item.speeches if not take(s, item.slug)]
    if not unmatched:
        return matched
    # The protocol files this debate under another item: the block where the
    # most of the remaining speakers spoke. Distinct speakers, not speeches,
    # or the Befragung, where the same members ask many questions, would win.
    speakers = {speaker_slug(s) for s in unmatched}
    in_block: dict[str, set[str]] = {}
    for p in index.speeches:
        if p.speaker in speakers:
            in_block.setdefault(p.agenda, set()).add(p.speaker)
    if in_block:
        block = max(in_block, key=lambda agenda: len(in_block[agenda]))
        for speech in unmatched:
            take(speech, block)
    return matched


def _drop_twins(
    items: list[AgendaItem], matches: dict[str, ProtocolSpeech]
) -> set[str]:
    """source_item_ids of speeches that are another speech's twin from the
    other source: same protocol speech, the openparliament.tv one wins."""
    by_position: dict[int, list[Speech]] = {}
    for item in items:
        for speech in item.speeches:
            if (found := matches.get(speech.source_item_id)) is not None:
                by_position.setdefault(found.position, []).append(speech)
    dropped: set[str] = set()
    for twins in by_position.values():
        if len(twins) < 2:
            continue
        keep = next((s for s in twins if s.source == "op"), twins[0])
        dropped.update(s.source_item_id for s in twins if s is not keep)
    return dropped


def _order(
    speeches: list[Speech], matches: dict[str, ProtocolSpeech], pdf_base: str
) -> list[Speech]:
    """Protocol order, page anchors filled in. A speech the protocol does not
    list goes last, in the stable order it came in."""
    placed: list[tuple[int, Speech]] = []
    unplaced: list[Speech] = []
    for speech in speeches:
        found = matches.get(speech.source_item_id)
        if found is None:
            unplaced.append(speech)
            continue
        if found.page is not None and not speech.protocol_page_url:
            speech.protocol_page_url = f"{pdf_base}#page={found.page}"
        placed.append((found.position, speech))
    if unplaced:
        logger.warning(
            "%d speech(es) not found in protocol %s: %s",
            len(unplaced),
            pdf_base,
            [s.speech_key for s in unplaced],
        )
    return [s for _, s in sorted(placed, key=lambda p: p[0])] + unplaced


def apply_protocols(sitting: SittingDay, fetch: FetchText = fetch_text) -> int:
    """Put each agenda item's speeches into protocol order, link them to their
    protocol page and drop the twin of a speech both sources hold; returns how
    many agenda items are now ordered.

    An item whose protocol cannot be fetched or parsed stays unordered, and
    the builder leaves it for a later run.
    """
    ordered = 0
    for protocol_id, pdf_url in sitting.protocols:
        match = _PROTOCOL_ID_RE.match(protocol_id)
        xml_url = protocol_xml_url(pdf_url) if pdf_url else None
        if not match or not xml_url:
            continue
        session = (int(match.group(1)), int(match.group(2)))
        try:
            index = protocol_index(fetch(xml_url))
        except Exception as exc:  # noqa: BLE001
            logger.warning("No protocol order for %s: %s", protocol_id, exc)
            continue
        if not index.speeches:
            logger.warning("Protocol %s lists no speeches yet", protocol_id)
            continue
        if index.session_date and index.session_date != sitting.day:
            logger.warning(
                "Protocol %s is dated %s, its speeches %s",
                protocol_id,
                index.session_date,
                sitting.day,
            )
        items = [i for i in sitting.agenda_items if i.session == session]
        matches: dict[str, ProtocolSpeech] = {}
        for item in items:
            matches.update(_match_item(item, index))
        twins = _drop_twins(items, matches)
        pdf_base = xml_url[: -len(".xml")] + ".pdf"
        for item in items:
            item.speeches = _order(
                [s for s in item.speeches if s.source_item_id not in twins],
                matches,
                pdf_base,
            )
            item.ordered = True
            if item.speeches and not any(
                s.source_item_id in matches for s in item.speeches
            ):
                # The protocol lists none of it: no debate the protocol knows
                # (e.g. the chair's remarks filed as speeches), so no item.
                logger.warning(
                    "%s (%s) is not in protocol %s; left out",
                    item.label,
                    item.key,
                    protocol_id,
                )
                item.speeches = []
            ordered += bool(item.speeches)
        sitting.agenda_items = [i for i in sitting.agenda_items if i.speeches]
    return ordered
