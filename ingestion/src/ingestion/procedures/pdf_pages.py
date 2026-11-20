# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""PDF pages for Drucksache chunks and Plenarprotokoll stages.

DIP's ``drucksache-text`` has no page breaks, so a chunk's pages are found by
looking up its first and last letters in the PDF, with the matcher the feed
uses for speeches (``ProtocolPdf``). A protocol stage carries the printed
page ("13554C"); the PDF's page labels turn it into a PDF page. Where nothing
matches, the page stays unset.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Optional

import requests

from ingestion.connectors.bundestag_speeches.client import fetch_bytes
from ingestion.feed.protocol_pages import ProtocolPdf
from wahlchat_common.procedures import ProcedureRecord, ProcedureStage

logger = logging.getLogger(__name__)

_HOST = "https://dserver.bundestag.de/"
_SAFE_PATH = re.compile(r"^[\w/.-]+\.pdf$")
# Printed on every page of a pre-print and kept in DIP's text where the page
# broke, so it is no part of the passage the PDF holds.
_WATERMARK = re.compile(
    r"V\s?orabfassung\s*[-–]\s*w\s?ird durch die lektorierte Fassung ersetzt\.?"
)
# Fewer letters than this match too many places to place a chunk.
_MIN_LETTERS = 16
_PRINTED_PAGE = re.compile(r"^(\d+)")
_PARSED_KEPT = 4
# A PDF is held in memory and parsed whole, and a Haushalt Gesetzentwurf is
# over 250 MB: more than a 1 GiB job survives. Protocols and ordinary
# Drucksachen are a few MB, so a larger PDF only costs its pages, which stay
# unset.
MAX_PDF_BYTES = 50 * 1024 * 1024

Pages = tuple[Optional[int], Optional[int]]


def fetch_pdf(url: str) -> bytes:
    return fetch_bytes(url, max_bytes=MAX_PDF_BYTES)


class PdfSource:
    """dserver PDFs, fetched at most once per ``min_interval`` seconds with a
    backoff when the server pushes back, and kept in ``cache_dir`` if given."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        *,
        fetch: Callable[[str], bytes] = fetch_pdf,
        min_interval: float = 1.0,
        backoff: Sequence[float] = (10.0, 60.0),
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._dir = cache_dir
        self._fetch = fetch
        self._min_interval = min_interval
        self._backoff = backoff
        self._sleep = sleep
        self._clock = clock
        self._last_fetch: Optional[float] = None
        self._parsed: OrderedDict[str, Optional[ProtocolPdf]] = OrderedDict()
        self.fetched = 0

    @staticmethod
    def _relative(url: str) -> Optional[str]:
        """The path on dserver; None for anything not a dserver PDF."""
        base = url.split("#", 1)[0]
        if not base.startswith(_HOST):
            return None
        rel = base[len(_HOST) :]
        return None if ".." in rel or not _SAFE_PATH.match(rel) else rel

    def _wait_turn(self) -> None:
        if self._last_fetch is not None:
            wait = self._min_interval - (self._clock() - self._last_fetch)
            if wait > 0:
                self._sleep(wait)
        self._last_fetch = self._clock()

    def _download(self, url: str) -> bytes:
        for pause in [*self._backoff, None]:
            self._wait_turn()
            try:
                return self._fetch(url)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if pause is None or status not in (429, 500, 502, 503, 504):
                    raise
                logger.warning("%s answered %s; waiting %.0fs", url, status, pause)
                self._sleep(pause)
        raise AssertionError("unreachable")

    def read(self, url: str) -> Optional[bytes]:
        rel = self._relative(url)
        if rel is None:
            return None
        path = self._dir / rel if self._dir is not None else None
        if path is not None and path.exists():
            return path.read_bytes()
        try:
            data = self._download(url.split("#", 1)[0])
        except Exception as exc:  # noqa: BLE001 (the page stays unset; tried again later)
            logger.warning("No PDF %s: %s", url, exc)
            return None
        self.fetched += 1
        if not data.startswith(b"%PDF"):
            logger.warning("Not a PDF: %s", url)
            return None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(f".{os.getpid()}.part")
            partial.write_bytes(data)
            partial.replace(path)
        return data

    def pdf(self, url: str) -> Optional[ProtocolPdf]:
        """The parsed PDF, kept for the last few URLs asked for."""
        key = url.split("#", 1)[0]
        if key in self._parsed:
            self._parsed.move_to_end(key)
            return self._parsed[key]
        data = self.read(key)
        parsed: Optional[ProtocolPdf] = None
        if data is not None:
            try:
                parsed = ProtocolPdf.from_bytes(data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unreadable PDF %s: %s", key, exc)
        self._parsed[key] = parsed
        if len(self._parsed) > _PARSED_KEPT:
            self._parsed.popitem(last=False)
        return parsed


def _searchable(passage: str) -> str:
    return _WATERMARK.sub(" ", passage)


def passage_pages(passages: Sequence[str], pdf: ProtocolPdf) -> list[Pages]:
    """(page_start, page_end) of each passage, in document order; page_end
    only when the passage runs onto a later page. Each search starts at the
    previous passage's page, so repeated phrases resolve to the nearer one."""
    out: list[Pages] = []
    first = 1
    for passage in passages:
        text = _searchable(passage)
        if sum(ch.isalpha() for ch in text) < _MIN_LETTERS:
            out.append((None, None))
            continue
        start, end = pdf.pages_of(text, first)
        first = start or first
        out.append((start, end))
    return out


def printed_page(page: Optional[str]) -> Optional[int]:
    match = _PRINTED_PAGE.match(page or "")
    return int(match.group(1)) if match else None


def _protocol_key(stage: ProcedureStage) -> Optional[tuple[str, int]]:
    printed = printed_page(stage.page)
    if stage.document_kind != "Plenarprotokoll" or not stage.url or printed is None:
        return None
    return stage.url.split("#", 1)[0], printed


def stage_pdf_pages(
    records: Iterable[ProcedureRecord],
    pdfs: PdfSource,
    previous: Optional[dict[str, ProcedureRecord]] = None,
) -> list[ProcedureRecord]:
    """The records with each stage's PDF page filled in: page 1 for a
    Drucksache, the labelled page for a Plenarprotokoll.

    A page the previous record already had for the same printed page is
    kept; the rest are looked up one protocol at a time.
    """
    records = list(records)
    known: dict[tuple[str, int], int] = {}
    for record in (previous or {}).values():
        for stage in record.stages:
            key = _protocol_key(stage)
            if key is not None and stage.pdf_page is not None:
                known[key] = stage.pdf_page
    wanted = {
        key
        for record in records
        for stage in record.stages
        if (key := _protocol_key(stage)) is not None and key not in known
    }
    by_url: dict[str, set[int]] = {}
    for url, printed in wanted:
        by_url.setdefault(url, set()).add(printed)
    for url, printed_pages in sorted(by_url.items()):
        pdf = pdfs.pdf(url)
        if pdf is None:
            continue
        for printed in printed_pages:
            if (page := pdf.page(printed)) is not None:
                known[(url, printed)] = page

    def placed(stage: ProcedureStage) -> ProcedureStage:
        if stage.document_kind == "Drucksache" and stage.pdf_page is None:
            return stage.model_copy(update={"pdf_page": 1})
        key = _protocol_key(stage)
        if key is not None and key in known:
            return stage.model_copy(update={"pdf_page": known[key]})
        return stage

    return [
        record.model_copy(update={"stages": [placed(s) for s in record.stages]})
        for record in records
    ]
