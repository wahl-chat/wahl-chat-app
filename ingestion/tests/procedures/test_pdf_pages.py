# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""PDF pages of Drucksache chunks and protocol stages, and their backfill.

``drucksache_21_8457.pdf`` is the dserver PDF of the fixture's text."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import requests
from pypdf import PdfWriter

from ingestion.feed import protocol_pages
from ingestion.feed.protocol_pages import ProtocolPdf
from ingestion.ids import compute_chunk_id
from ingestion.procedures.drucksachen import drucksache_chunks
from ingestion.procedures.mapper import build_record
from ingestion.procedures.page_backfill import (
    PageReport,
    Progress,
    backfill_chunks,
    backfill_stages,
    stored_report,
)
from ingestion.procedures.pdf_pages import PdfSource, passage_pages, stage_pdf_pages
from ingestion.procedures.store import ProcedureStore
from wahlchat_common.procedures import ProcedureRecord, ProcedureStage

from .conftest import FIXTURES, load
from .fakes import FakeFirestore, FakeQdrant

TODAY = date(2026, 11, 18)
DOC_URL = "https://dserver.bundestag.de/btd/21/084/2108457.pdf"
PROTOCOL_URL = "https://dserver.bundestag.de/btp/21/21089.pdf"
PDF_8457 = (FIXTURES / "drucksache_21_8457.pdf").read_bytes()
# Page of each chunk of 21/8457 (start, end when it runs on). The last one
# ends with the printer's imprint on page 8.
PAGES_8457 = [
    (1, None), (1, None), (1, None), (1, 2), (2, None), (2, None), (2, None),
    (4, None), (4, None), (4, None), (4, None), (4, None), (4, None), (4, None),
    (5, 8),
]  # fmt: skip


def _protocol_pdf(pages: int = 5) -> bytes:
    """Two contents pages, then printed pages from 10741 on."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    writer.set_page_label(0, 1, style="/R")
    writer.set_page_label(2, pages - 1, style="/D", start=10741)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class _Fetch:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        if url not in self.files:
            raise requests.HTTPError(response=_Response(404))
        return self.files[url]


class _Response:
    def __init__(self, status: int) -> None:
        self.status_code = status


def _source(tmp_path: Path, files: dict[str, bytes]) -> tuple[PdfSource, _Fetch]:
    fetch = _Fetch(files)
    return PdfSource(
        tmp_path, fetch=fetch, min_interval=0, sleep=lambda _s: None
    ), fetch


def _chunks(pdf: ProtocolPdf | None = None) -> list[Any]:
    return drucksache_chunks(
        load("drucksache_21_8457"), procedures={}, today=TODAY, pdf=pdf
    )


# --- chunk pages ---


def test_each_chunk_gets_the_pdf_pages_it_sits_on() -> None:
    chunks = _chunks(ProtocolPdf.from_bytes(PDF_8457))
    pages = [(c.meta.get("page_start"), c.meta.get("page_end")) for c in chunks]
    assert pages == PAGES_8457
    assert {c.doc_section for c in chunks if c.meta["page_start"] >= 4} == {"report"}


def test_pages_leave_the_content_hash_alone() -> None:
    with_pages = _chunks(ProtocolPdf.from_bytes(PDF_8457))
    without = _chunks()
    assert "page_start" not in without[0].meta
    assert [c.content_hash for c in with_pages] == [c.content_hash for c in without]


def _pdf_with_texts(texts: dict[int, str]) -> ProtocolPdf:
    pdf = ProtocolPdf.from_bytes(_protocol_pdf())
    pdf._texts = {n: protocol_pages._letters(t) for n, t in texts.items()}
    return pdf


def test_the_preprint_watermark_does_not_hide_a_chunk() -> None:
    # DIP's text keeps the watermark where the page broke; the PDF prints it
    # elsewhere on the page.
    pdf = _pdf_with_texts(
        {
            1: "Erster Teil des Antrags.",
            2: "6. bundesweite Standards für alle Aspekte einer effektiven "
            "Gefährdungsanalyse Vorabfassung – wird durch die lektorierte "
            "Fassung ersetzt.",
        }
    )
    passage = (
        "V orabfassung – w ird durch die lektorierte Fassung ersetzt.\n"
        "6. bundesweite Standards für alle Aspekte einer effektiven "
        "Gefährdungsanalyse"
    )
    assert passage_pages([passage], pdf) == [(2, None)]


def test_a_passage_the_pdf_lacks_or_too_short_to_place_gets_no_page() -> None:
    pdf = _pdf_with_texts({1: "Etwas ganz anderes steht hier.", 2: "Ja."})
    assert passage_pages(
        ["Dieser Satz steht in keinem der beiden Seitentexte.", "Ja."], pdf
    ) == [(None, None), (None, None)]


# --- stage pages ---


def _stage(position_id: str, **kw: Any) -> ProcedureStage:
    return ProcedureStage(
        position_id=position_id, date=date(2026, 7, 9), chamber="BT", name="x", **kw
    )


def _record(stages: list[ProcedureStage]) -> ProcedureRecord:
    record = build_record(
        {"id": "1", "wahlperiode": 21, "vorgangstyp": "Gesetzgebung", "titel": "T"},
        [],
        previous=None,
        today=TODAY,
    )
    return record.model_copy(update={"stages": stages})


def _stages() -> list[ProcedureStage]:
    return [
        _stage("1", document_kind="Drucksache", document_number="21/1"),
        _stage(
            "2",
            document_kind="Plenarprotokoll",
            page="10742C",
            url=f"{PROTOCOL_URL}#P.10742",
        ),
        _stage("3", document_kind="Plenarprotokoll", page="99999", url=PROTOCOL_URL),
    ]


def test_protocol_stages_get_the_pdf_page_of_their_printed_page(tmp_path: Path) -> None:
    pdfs, fetch = _source(tmp_path, {PROTOCOL_URL: _protocol_pdf()})
    [placed] = stage_pdf_pages([_record(_stages())], pdfs)
    # Printed 10742 is PDF page 4 (two contents pages); 99999 is not in it.
    assert [s.pdf_page for s in placed.stages] == [1, 4, None]
    assert fetch.calls == [PROTOCOL_URL]


def test_a_known_page_is_kept_without_a_download(tmp_path: Path) -> None:
    pdfs, fetch = _source(tmp_path, {})
    old = _record([s.model_copy(update={"pdf_page": 4}) for s in _stages()[:2]])
    [placed] = stage_pdf_pages([_record(_stages()[:2])], pdfs, {"1": old})
    assert [s.pdf_page for s in placed.stages] == [1, 4]
    assert fetch.calls == []


def test_stage_pages_leave_the_record_hash_alone(tmp_path: Path) -> None:
    from ingestion.procedures.mapper import _record_hash

    pdfs, _ = _source(tmp_path, {PROTOCOL_URL: _protocol_pdf()})
    record = _record(_stages())
    [placed] = stage_pdf_pages([record], pdfs)
    assert placed.stages != record.stages
    assert _record_hash(placed) == _record_hash(record)


# --- the PDF source ---


def test_pdfs_are_cached_on_disk(tmp_path: Path) -> None:
    pdfs, fetch = _source(tmp_path, {DOC_URL: PDF_8457})
    assert pdfs.read(DOC_URL) == PDF_8457
    assert (tmp_path / "btd/21/084/2108457.pdf").read_bytes() == PDF_8457
    again, fetch_again = _source(tmp_path, {})
    assert again.read(DOC_URL) == PDF_8457
    assert fetch.calls == [DOC_URL] and fetch_again.calls == []


def test_only_dserver_pdfs_are_fetched(tmp_path: Path) -> None:
    pdfs, fetch = _source(tmp_path, {})
    assert pdfs.read("https://example.org/a.pdf") is None
    assert pdfs.read("https://dserver.bundestag.de/../etc/passwd.pdf") is None
    assert fetch.calls == []


def test_downloads_are_spaced_and_back_off_when_pushed_back(tmp_path: Path) -> None:
    slept: list[float] = []
    answers: list[Any] = [
        requests.HTTPError(response=_Response(429)),
        PDF_8457,
        PDF_8457,
    ]

    def fetch(_url: str) -> bytes:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    pdfs = PdfSource(
        tmp_path, fetch=fetch, min_interval=2.0, backoff=(10.0,),
        sleep=slept.append, clock=lambda: 100.0,
    )  # fmt: skip
    assert pdfs.read(DOC_URL) == PDF_8457
    assert pdfs.read(DOC_URL.replace("2108457", "2108458")) == PDF_8457
    # 10 s after the 429; 2 s before each later download.
    assert slept == [10.0, 2.0, 2.0]


def test_a_failed_download_leaves_nothing_in_the_cache(tmp_path: Path) -> None:
    pdfs, _ = _source(tmp_path, {})
    assert pdfs.pdf(DOC_URL) is None
    assert not list(tmp_path.rglob("*.pdf"))


# --- backfill ---


def _stored(qdrant: FakeQdrant) -> list[Any]:
    chunks = _chunks()
    for chunk in chunks:
        qdrant.add(
            str(compute_chunk_id(chunk.source_item_id, chunk.chunk_index)),
            chunk.model_dump(mode="json", exclude_none=True),
        )
    return chunks


def test_backfill_writes_pages_into_meta_only(tmp_path: Path) -> None:
    qdrant = FakeQdrant()
    chunks = _stored(qdrant)
    before = {pid: dict(p) for pid, p in qdrant.points.items()}
    pdfs, _ = _source(tmp_path, {DOC_URL: PDF_8457})
    report = backfill_chunks(qdrant, "c", pdfs, Progress(tmp_path / "done"))

    assert qdrant.upserts == [] and qdrant.deletes == []
    assert {k for payload, _ in qdrant.payload_writes for k in payload} == {
        "page_start",
        "page_end",
    }
    for pid, payload in qdrant.points.items():
        assert payload["text"] == before[pid]["text"]
        assert payload["content_hash"] == before[pid]["content_hash"]
    by_index = sorted(qdrant.points.values(), key=lambda p: p["chunk_index"])
    pages = [(p["meta"].get("page_start"), p["meta"].get("page_end")) for p in by_index]
    assert pages == PAGES_8457
    assert report.documents == 1
    assert sum(row[1] for row in report.chunks.values()) == len(chunks)


def test_backfill_is_idempotent_and_resumes(tmp_path: Path) -> None:
    qdrant = FakeQdrant()
    _stored(qdrant)
    pdfs, fetch = _source(tmp_path, {DOC_URL: PDF_8457})
    backfill_chunks(qdrant, "c", pdfs, Progress(tmp_path / "done"))
    first = {pid: dict(p) for pid, p in qdrant.points.items()}
    writes = len(qdrant.payload_writes)

    # Resumed: the placed document is not read again.
    backfill_chunks(qdrant, "c", pdfs, Progress(tmp_path / "done"))
    assert len(qdrant.payload_writes) == writes and fetch.calls == [DOC_URL]

    # Run afresh: the same pages, from the cached PDF.
    backfill_chunks(qdrant, "c", pdfs, Progress(tmp_path / "again"))
    assert qdrant.points == first and fetch.calls == [DOC_URL]


def test_a_document_without_a_pdf_is_tried_again(tmp_path: Path) -> None:
    qdrant = FakeQdrant()
    _stored(qdrant)
    progress = Progress(tmp_path / "done")
    pdfs, _ = _source(tmp_path, {})
    report = backfill_chunks(qdrant, "c", pdfs, progress)
    assert report.no_pdf == ["drucksache:BT:21/8457"] and progress.done == set()
    assert qdrant.payload_writes == []


def test_the_stored_report_counts_by_type_and_section(tmp_path: Path) -> None:
    qdrant = FakeQdrant()
    _stored(qdrant)
    pdfs, _ = _source(tmp_path, {DOC_URL: PDF_8457})
    backfill_chunks(qdrant, "c", pdfs, Progress(tmp_path / "done"))
    report = stored_report(qdrant, "c")
    assert report.chunks == {
        ("Beschlussempfehlung und Bericht", "overview"): [7, 7, 1],
        ("Beschlussempfehlung und Bericht", "report"): [8, 8, 1],
    }
    assert "100.0%" in report.render()


def test_stage_backfill_writes_stages_only_and_once(tmp_path: Path) -> None:
    db = FakeFirestore()
    store = ProcedureStore(db)
    record = _record(_stages())
    store.put([record])
    pdfs, _ = _source(tmp_path, {PROTOCOL_URL: _protocol_pdf()})

    report = backfill_stages(store, pdfs, PageReport())
    stored = store.get(["1"])["1"]
    assert [s.pdf_page for s in stored.stages] == [1, 4, None]
    assert stored.content_hash == record.content_hash
    assert (report.stages, report.stages_placed, report.records_written) == (2, 1, 1)

    again = backfill_stages(store, pdfs, PageReport())
    assert again.records_written == 0


def test_stage_backfill_keeps_fields_it_does_not_know(tmp_path: Path) -> None:
    db = FakeFirestore()
    store = ProcedureStore(db)
    store.put([_record(_stages())])
    db.collection("procedures").document("1").update({"step_summaries": {"a": 1}})
    pdfs, _ = _source(tmp_path, {PROTOCOL_URL: _protocol_pdf()})

    backfill_stages(store, pdfs, PageReport())
    raw = db.collection("procedures").document("1").get().to_dict()
    assert raw["step_summaries"] == {"a": 1}
    assert [s["pdf_page"] for s in raw["stages"]] == [1, 4, None]


@pytest.mark.parametrize("kind", ["Drucksache", "Plenarprotokoll"])
def test_mapped_drucksache_stages_start_on_page_one(
    kind: str, positions: dict[str, Any], vorgaenge: dict[str, Any]
) -> None:
    record = build_record(
        vorgaenge["320784"], positions["320784"], previous=None, today=TODAY
    )
    stages = [s for s in record.stages if s.document_kind == kind]
    assert stages
    assert all(s.pdf_page == (1 if kind == "Drucksache" else None) for s in stages)
