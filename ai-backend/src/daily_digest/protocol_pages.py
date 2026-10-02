# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Page anchors into the Plenarprotokoll PDF for every speech of a sitting.

Bundestag speeches in the corpus are mostly openparliament.tv records: they
carry the video, and their DIP twin (the only source with a protocol page) was
merged away at ingest, leaving just the bare PDF. The protocol XML next to that
PDF still lists every speech with its PDF page, and speeches are matched to it
through the shared ``speech_key``, so each speaker can link to the exact page.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

from src.daily_digest.reader import SittingDay
from src.ingestion.connectors.bundestag_speeches.client import fetch_text
from src.ingestion.connectors.bundestag_speeches.parser import parse_speeches_from_xml
from src.ingestion.speech_key import make_speech_key

logger = logging.getLogger(__name__)

# Bundestag protocol PDFs live at dserver.bundestag.de/btp/{wp}/{wp}{nnn}.pdf
# with the XML beside them; nothing else is rewritten into an XML URL.
_PROTOCOL_PDF_RE = re.compile(r"^https://dserver\.bundestag\.de/btp/\d+/\d+\.pdf$")
_PROTOCOL_ID_RE = re.compile(r"^(\d+)/(\d+)$")

FetchText = Callable[[str], str]


def protocol_xml_url(pdf_url: str) -> Optional[str]:
    base = pdf_url.split("#", 1)[0]
    if not _PROTOCOL_PDF_RE.match(base):
        return None
    return base[: -len(".pdf")] + ".xml"


def page_index(xml_text: str, ep: int, session: int) -> dict[str, int]:
    """speech_key → 1-based PDF page of that speech's start."""
    index: dict[str, int] = {}
    for speech in parse_speeches_from_xml(xml_text):
        page = speech.get("pdf_page")
        if not isinstance(page, int):
            continue
        key = make_speech_key(
            ep=ep,
            session=session,
            speaker_name=speech.get("speaker_name"),
            top_id=speech.get("agenda_top_id"),
        )
        # A speaker can take the floor twice under one agenda item; the first
        # speech is the one the reader is looking for.
        index.setdefault(key, page)
    return index


def attach_protocol_pages(sitting: SittingDay, fetch: FetchText = fetch_text) -> int:
    """Fill ``protocol_page_url`` on the sitting's speeches; returns how many.

    Best effort: a protocol whose XML cannot be fetched or parsed leaves its
    speeches on the bare PDF.
    """
    speeches = [s for item in sitting.agenda_items for s in item.speeches]
    attached = 0
    for protocol_id, pdf_url in sitting.protocols:
        match = _PROTOCOL_ID_RE.match(protocol_id)
        xml_url = protocol_xml_url(pdf_url) if pdf_url else None
        if not match or not xml_url:
            continue
        ep, session = int(match.group(1)), int(match.group(2))
        try:
            pages = page_index(fetch(xml_url), ep, session)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No page anchors for protocol %s: %s", protocol_id, exc)
            continue
        pdf_base = xml_url[: -len(".xml")] + ".pdf"
        for speech in speeches:
            if speech.protocol_page_url or speech.session_key != (ep, session):
                continue
            page = pages.get(speech.speech_key or "")
            if page is not None:
                speech.protocol_page_url = f"{pdf_base}#page={page}"
                attached += 1
    return attached
