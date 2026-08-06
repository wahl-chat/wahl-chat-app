# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Printed-page → physical-PDF-page resolution for plenary protocol PDFs.

Protocol PDFs prepend unnumbered front matter (title + table of contents)
before the first content page, whose printed number continues the
Wahlperiode-wide pagination. ``#page=N`` deep links address PHYSICAL pages,
so the arithmetic estimate ``printed − start + 1`` lands short by the
front-matter length — and only the PDF itself can reveal that length.

``resolve_page_offset`` tries page labels first, then a header text scan.
Label-derived offsets are always validated against known (printed, estimate)
sample pairs: many protocol PDFs carry plain ``1…N`` labels (physical
numbering), where a lookup finds the printed number at the wrong position.
"""

from __future__ import annotations

import io
import logging

import requests
from pypdf import PdfReader

from src.ingestion.connectors.bundestag_speeches.client import curl_get_bytes

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT_S = 60

# Front matter is a handful of pages; a wider search risks false header
# matches. Interior label runs get a looser bound (16-page front matter has
# been observed).
_MAX_OFFSET = 15
_MAX_INTERIOR_OFFSET = 30

# Header/footer tokens inspected per page for the printed page number.
_EDGE_TOKENS = 30


def fetch_pdf_reader(pdf_url: str) -> PdfReader | None:
    """Download a protocol PDF (fragment stripped); None on any failure —
    page resolution is citation polish, never a reason to drop a protocol."""
    url = pdf_url.split("#", 1)[0]
    try:
        response = requests.get(url, timeout=_FETCH_TIMEOUT_S)
        if ".enodia/challenge" in response.url:
            # Same WAF fallback as client.fetch_text — the challenge redirect
            # answers 200 with HTML, so raise_for_status() cannot catch it.
            pdf_bytes = curl_get_bytes(url, accept="application/pdf")
        else:
            response.raise_for_status()
            pdf_bytes = response.content
        return PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not fetch/read protocol PDF %s: %s", url, exc)
        return None


def read_page_labels(reader: PdfReader) -> list[str] | None:
    """The PDF's page labels, or None when unavailable/unreadable."""
    try:
        labels = list(reader.page_labels)
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not read PDF page labels: %s", exc)
        return None
    return labels if labels else None


def front_matter_offset(labels: list[str]) -> int | None:
    """Start index of the trailing contiguous printed run (= front-matter
    length), walking BACK from the last label.

    Walking backwards matters: stray numeric labels can occur inside the
    front matter (Protokoll 21/4 labels a title page ``4``). Plain ``1…N``
    label sets walk back to 0 — indistinguishable from "no front matter",
    hence the sample validation in ``offset_from_labels``.
    """
    if not labels or not labels[-1].isdigit():
        return None
    run_start = len(labels) - 1
    while run_start > 0:
        prev = labels[run_start - 1]
        if not prev.isdigit() or int(prev) != int(labels[run_start]) - 1:
            break
        run_start -= 1
    return run_start


def offset_from_labels(labels: list[str], samples: list[tuple[int, int]]) -> int | None:
    """Label-derived offset, accepted only when every (printed, estimate)
    sample resolves to exactly ``estimate + offset`` — rejects plain ``1…N``
    label sets."""
    if not samples:
        return None
    anchor = front_matter_offset(labels)
    if anchor is None or not 0 <= anchor <= _MAX_OFFSET:
        return None
    for printed, estimate in samples:
        try:
            physical = labels.index(str(printed), anchor) + 1
        except ValueError:
            return None
        if physical != estimate + anchor:
            return None
    return anchor


def _page_edge_tokens(reader: PdfReader, physical_page: int) -> list[str]:
    """Header/footer tokens of a 1-based physical page ([] when unreadable)."""
    if physical_page < 1 or physical_page > len(reader.pages):
        return []
    try:
        text = reader.pages[physical_page - 1].extract_text() or ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not extract text of PDF page %d: %s", physical_page, exc)
        return []
    tokens = text.split()
    return tokens[:_EDGE_TOKENS] + tokens[-_EDGE_TOKENS:]


def offset_from_header_scan(
    reader: PdfReader, samples: list[tuple[int, int]]
) -> int | None:
    """Offset from the printed number in page headers: scan forward from the
    first sample's estimate; every further sample must confirm the same
    offset on its own page."""
    if not samples:
        return None
    first_printed, first_estimate = samples[0]
    found: int | None = None
    for offset in range(0, _MAX_OFFSET + 1):
        if str(first_printed) in _page_edge_tokens(reader, first_estimate + offset):
            found = offset
            break
    if found is None:
        return None
    for printed, estimate in samples[1:]:
        if str(printed) not in _page_edge_tokens(reader, estimate + found):
            return None
    return found


def _longest_numeric_run_start(labels: list[str]) -> int | None:
    """Start of the longest strictly-consecutive numeric label run (≥3, so a
    stray pair can never win)."""
    best_start, best_len = None, 0
    i, n = 0, len(labels)
    while i < n:
        if labels[i].isdigit():
            j = i
            while (
                j + 1 < n
                and labels[j + 1].isdigit()
                and int(labels[j + 1]) == int(labels[j]) + 1
            ):
                j += 1
            if j - i + 1 > best_len:
                best_start, best_len = i, j - i + 1
            i = j + 1
        else:
            i += 1
    return best_start if best_len >= 3 else None


def offset_from_interior_label_run(
    labels: list[str], samples: list[tuple[int, int]]
) -> int | None:
    """Sample-validated offset from the longest printed run — tolerates label
    trees polluted by stray physical numbers, which break the tail-anchored
    walk of ``front_matter_offset``."""
    if not samples:
        return None
    start = _longest_numeric_run_start(labels)
    if start is None or not 0 <= start <= _MAX_INTERIOR_OFFSET:
        return None
    for printed, estimate in samples:
        try:
            physical = labels.index(str(printed), start) + 1
        except ValueError:
            return None
        if physical != estimate + start:
            return None
    return start


def resolve_page_offset(
    reader: PdfReader, samples: list[tuple[int, int]]
) -> int | None:
    """Front-matter offset for one protocol PDF, or None when undeterminable.

    ``samples`` are (printed, estimated physical) pairs — use a few with
    distinct printed pages; without samples the offset is undeterminable.
    """
    if not samples:
        return None
    labels = read_page_labels(reader)
    if labels is not None:
        offset = offset_from_labels(labels, samples)
        if offset is not None:
            return offset
    offset = offset_from_header_scan(reader, samples)
    if offset is not None:
        return offset
    if labels is not None:
        return offset_from_interior_label_run(labels, samples)
    return None
