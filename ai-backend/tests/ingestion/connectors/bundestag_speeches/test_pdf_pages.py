# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Printed→physical page resolution against protocol PDF page labels/headers.

Label shapes mirror real protocols: Protokoll 20/175 has six roman-labeled
front-matter pages before the printed run; Protokoll 21/4 additionally labels
a front-matter page with a bare digit (``4``); a large share of protocol PDFs
carry plain ``1…N`` labels (physical numbering), which must be rejected by
sample validation; and Protokoll 20/203 both pollutes its labels with physical
numbers AND has a gap in its printed run.
"""

from __future__ import annotations

from src.ingestion.connectors.bundestag_speeches import pdf_pages
from src.ingestion.connectors.bundestag_speeches.client import DipChallengeError
from src.ingestion.connectors.bundestag_speeches.pdf_pages import (
    fetch_pdf_reader,
    front_matter_offset,
    offset_from_header_scan,
    offset_from_interior_label_run,
    offset_from_labels,
    resolve_page_offset,
)

# Protokoll 20/175 shape: 6 roman pages, printed run starts at 22551.
_ROMAN_FRONT = ["I", "II", "III", "IV", "V", "VI"] + [
    str(n) for n in range(22551, 22561)
]

# Protokoll 21/4 shape: a stray numeric label INSIDE the front matter.
_STRAY_DIGIT_FRONT = ["I", "II", "III", "4"] + [str(n) for n in range(177, 183)]

# Plain physical labels — indistinguishable from "no front matter" by labels
# alone; only sample validation can reject them.
_PLAIN = [str(n) for n in range(1, 11)]

# Protokoll 20/203 shape: printed-style labels polluted by PHYSICAL numbers —
# one right before the printed run and one as the very last label — which
# breaks the tail-anchored walk but not the longest-run search.
_POLLUTED = ["I", "II", "III", "16"] + [str(n) for n in range(26123, 26133)] + ["15"]


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    """Minimal stand-in for PdfReader: page_labels + pages[i].extract_text()."""

    def __init__(self, labels: list[str] | None, page_texts: list[str]) -> None:
        self._labels = labels
        self.pages = [_FakePage(t) for t in page_texts]

    @property
    def page_labels(self) -> list[str]:
        if self._labels is None:
            raise KeyError("no /PageLabels")
        return self._labels


def _protocol_pages(front: int, start_printed: int, count: int) -> list[str]:
    """Front-matter pages then content pages with a printed header number."""
    pages = ["Inhaltsverzeichnis" for _ in range(front)]
    for n in range(start_printed, start_printed + count):
        pages.append(f"Deutscher Bundestag – 20. Wahlperiode {n} Sitzungsbericht text")
    return pages


class TestFrontMatterOffset:
    def test_roman_front_matter(self) -> None:
        assert front_matter_offset(_ROMAN_FRONT) == 6

    def test_stray_digit_in_front_matter_is_not_part_of_the_run(self) -> None:
        # Counting non-numeric labels from the front would say 3; the backward
        # contiguous walk correctly stops at the 4→177 discontinuity.
        assert front_matter_offset(_STRAY_DIGIT_FRONT) == 4

    def test_plain_labels_walk_back_to_zero(self) -> None:
        assert front_matter_offset(_PLAIN) == 0

    def test_trailing_non_numeric_label_means_no_anchor(self) -> None:
        assert front_matter_offset(["1", "2", "Anlage"]) is None

    def test_empty(self) -> None:
        assert front_matter_offset([]) is None


class TestOffsetFromLabels:
    def test_printed_labels_validate_and_resolve(self) -> None:
        # printed 22552 was estimated at physical 2 (22552-22551+1); labels put
        # it at physical 8 → offset 6, consistent with the front-matter walk.
        assert offset_from_labels(_ROMAN_FRONT, [(22552, 2)]) == 6

    def test_stray_digit_case(self) -> None:
        assert offset_from_labels(_STRAY_DIGIT_FRONT, [(178, 2)]) == 4

    def test_plain_labels_are_rejected_by_sample_validation(self) -> None:
        # Plain 1…N labels contain the printed number as a LABEL, but at the
        # wrong physical position — the sample (printed 7 estimated at 5)
        # must reject them instead of "confirming" offset 0.
        assert offset_from_labels(_PLAIN, [(7, 5)]) is None

    def test_missing_printed_page_rejects(self) -> None:
        assert offset_from_labels(_ROMAN_FRONT, [(99999, 3)]) is None

    def test_no_samples_rejects(self) -> None:
        assert offset_from_labels(_ROMAN_FRONT, []) is None


class TestOffsetFromHeaderScan:
    def test_finds_offset_in_window(self) -> None:
        reader = _FakeReader(
            None, _protocol_pages(front=5, start_printed=880, count=20)
        )
        # printed 883 estimated at physical 4 (883-880+1); truly at 4+5.
        assert offset_from_header_scan(reader, [(883, 4)]) == 5

    def test_second_sample_must_confirm(self) -> None:
        pages = _protocol_pages(front=5, start_printed=880, count=20)
        # Corrupt the header of the page where the second sample must confirm:
        # printed 889 estimated at 10 → physical 15 (index 14).
        pages[14] = "kein Kopf"
        reader = _FakeReader(None, pages)
        assert offset_from_header_scan(reader, [(883, 4), (889, 10)]) is None

    def test_no_match_in_window_returns_none(self) -> None:
        reader = _FakeReader(None, ["nichts" for _ in range(30)])
        assert offset_from_header_scan(reader, [(883, 4)]) is None


class TestOffsetFromInteriorLabelRun:
    def test_polluted_labels_resolve_via_longest_run(self) -> None:
        # Tail-anchored walk fails on the trailing physical "15"; the longest
        # consecutive run (26123…) starts at index 4 → offset 4, and the
        # sample (printed 26125 estimated at 3 → physical 7) validates it.
        assert front_matter_offset(_POLLUTED) == len(_POLLUTED) - 1  # useless
        assert offset_from_interior_label_run(_POLLUTED, [(26125, 3)]) == 4

    def test_sample_disagreement_rejects(self) -> None:
        assert offset_from_interior_label_run(_POLLUTED, [(26125, 9)]) is None

    def test_no_samples_rejects(self) -> None:
        assert offset_from_interior_label_run(_POLLUTED, []) is None


class TestResolvePageOffset:
    def test_prefers_validated_labels(self) -> None:
        reader = _FakeReader(_ROMAN_FRONT, ["x" for _ in range(len(_ROMAN_FRONT))])
        assert resolve_page_offset(reader, [(22552, 2)]) == 6

    def test_falls_back_to_header_scan_for_plain_labels(self) -> None:
        pages = _protocol_pages(front=5, start_printed=880, count=20)
        reader = _FakeReader([str(n) for n in range(1, len(pages) + 1)], pages)
        assert resolve_page_offset(reader, [(883, 4)]) == 5

    def test_no_samples_returns_none(self) -> None:
        # Every mode validates against samples — none means no verdict.
        reader = _FakeReader(None, _protocol_pages(front=3, start_printed=50, count=10))
        assert resolve_page_offset(reader, []) is None


class _FakeResponse:
    def __init__(self, url: str, content: bytes) -> None:
        self.url = url
        self.content = content

    def raise_for_status(self) -> None:
        pass


class TestFetchPdfReader:
    """The .enodia/challenge WAF answers 200 with HTML, so raise_for_status()
    cannot catch it — fetch_pdf_reader must fall back to curl like fetch_text."""

    def test_challenge_redirect_falls_back_to_curl(self, monkeypatch) -> None:
        monkeypatch.setattr(
            pdf_pages.requests,
            "get",
            lambda url, timeout: _FakeResponse(
                "https://www.bundestag.de/.enodia/challenge?uri=x", b"<html>"
            ),
        )
        curl_args: dict = {}

        def _fake_curl(url: str, accept: str = "*/*") -> bytes:
            curl_args["call"] = (url, accept)
            return b"%PDF-fake"

        monkeypatch.setattr(pdf_pages, "curl_get_bytes", _fake_curl)
        seen: dict = {}
        monkeypatch.setattr(
            pdf_pages, "PdfReader", lambda buf: seen.setdefault("bytes", buf.getvalue())
        )

        result = fetch_pdf_reader(
            "https://dserver.bundestag.de/btp/21/21004.pdf#page=5"
        )

        assert result == b"%PDF-fake"  # the fake PdfReader echoes its input
        assert seen["bytes"] == b"%PDF-fake"
        assert curl_args["call"] == (
            "https://dserver.bundestag.de/btp/21/21004.pdf",  # fragment stripped
            "application/pdf",
        )

    def test_no_challenge_uses_response_content(self, monkeypatch) -> None:
        monkeypatch.setattr(
            pdf_pages.requests,
            "get",
            lambda url, timeout: _FakeResponse(url, b"%PDF-direct"),
        )

        def _fail_curl(url: str, accept: str = "*/*") -> bytes:
            raise AssertionError("curl fallback must not run without a challenge")

        monkeypatch.setattr(pdf_pages, "curl_get_bytes", _fail_curl)
        monkeypatch.setattr(pdf_pages, "PdfReader", lambda buf: buf.getvalue())

        result = fetch_pdf_reader("https://dserver.bundestag.de/btp/21/21004.pdf")
        assert result == b"%PDF-direct"

    def test_failed_curl_fallback_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(
            pdf_pages.requests,
            "get",
            lambda url, timeout: _FakeResponse(
                "https://www.bundestag.de/.enodia/challenge?uri=x", b"<html>"
            ),
        )

        def _raise(url: str, accept: str = "*/*") -> bytes:
            raise DipChallengeError("curl could not fetch")

        monkeypatch.setattr(pdf_pages, "curl_get_bytes", _raise)
        assert fetch_pdf_reader("https://dserver.bundestag.de/btp/21/21004.pdf") is None
