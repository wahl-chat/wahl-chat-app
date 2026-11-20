# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Write PDF pages onto stored Drucksache chunks and procedure stages.

    python -m ingestion.procedures.page_backfill                # everything
    python -m ingestion.procedures.page_backfill --limit 200    # a sample
    python -m ingestion.procedures.page_backfill --report       # match rate only

Payload-only: chunks get ``meta.page_start``/``meta.page_end`` through
``set_payload``, stages their ``pdf_page`` in Firestore. No vector, chunk
or content hash changes. Documents are taken in a fixed spread order, so
``--limit`` is a sample across types and Wahlperioden. A document with a
placed chunk is skipped, so a stopped run goes on where it stopped; one
whose PDF could not be read is tried again.
"""

from __future__ import annotations

if __name__ == "__main__":
    from ingestion.env_file import load_env_file

    load_env_file()

import argparse
import hashlib
import logging
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from qdrant_client import QdrantClient, models

from ingestion.firestore_guard import guard_firestore_target
from ingestion.procedures.drucksachen import stored_drucksachen
from ingestion.procedures.pdf_pages import PdfSource, passage_pages, stage_pdf_pages
from ingestion.procedures.store import ProcedureStore
from ingestion.schemas import SourceType
from ingestion.setup_collection import COLLECTION_NAME

logger = logging.getLogger(__name__)

_PAYLOAD = ["text", "meta", "chunk_index", "doc_section"]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_SCROLL = 1000


@dataclass
class PageReport:
    documents: int = 0
    no_pdf: list[str] = field(default_factory=list)
    # (doc_type, doc_section) -> [chunks, with page_start, with page_end]
    chunks: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    stages: int = 0
    stages_placed: int = 0
    records_written: int = 0

    def count(self, payload: dict[str, Any]) -> None:
        meta = payload.get("meta") or {}
        key = (str(meta.get("doc_type") or "?"), str(payload.get("doc_section") or "?"))
        row = self.chunks.setdefault(key, [0, 0, 0])
        row[0] += 1
        row[1] += meta.get("page_start") is not None
        row[2] += meta.get("page_end") is not None

    def render(self) -> str:
        if not self.chunks:
            return "\n".join(self._footer())
        lines = [
            "| doc_type | doc_section | chunks | page_start | rate | page_end |",
            "|---|---|---:|---:|---:|---:|",
        ]
        total = [0, 0, 0]
        for (doc_type, section), row in sorted(self.chunks.items()):
            total = [a + b for a, b in zip(total, row)]
            lines.append(
                f"| {doc_type} | {section} | {row[0]} | {row[1]} | {_rate(row)} | {row[2]} |"
            )
        lines.append(
            f"| **all** | | {total[0]} | {total[1]} | {_rate(total)} | {total[2]} |"
        )
        return "\n".join(lines + self._footer())

    def _footer(self) -> list[str]:
        lines: list[str] = []
        if self.documents or self.no_pdf:
            lines.append(
                f"\ndocuments placed: {self.documents}, without a readable PDF: {len(self.no_pdf)}"
            )
        if self.stages:
            lines.append(
                f"protocol stages with a PDF page: {self.stages_placed}/{self.stages}, "
                f"records written: {self.records_written}"
            )
        return lines


def _rate(row: list[int]) -> str:
    return f"{row[1] / row[0]:.1%}" if row[0] else "-"


def _spread(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _drucksache_filter(extra: Optional[models.FieldCondition] = None) -> models.Filter:
    must: list[Any] = [
        models.FieldCondition(
            key="source_type",
            match=models.MatchValue(value=SourceType.DRUCKSACHE.value),
        )
    ]
    if extra is not None:
        must.append(extra)
    return models.Filter(must=must)


def _placed(qdrant: Any, collection: str) -> set[str]:
    """Parents with at least one chunk that has a page."""
    flt = _drucksache_filter()
    flt.must_not = [
        models.IsEmptyCondition(is_empty=models.PayloadField(key="meta.page_start"))
    ]
    result = qdrant.facet(
        collection_name=collection,
        key="source_parent_key",
        facet_filter=flt,
        limit=1_000_000,
        exact=True,
    )
    return {str(hit.value) for hit in result.hits}


def _scroll(
    qdrant: Any, collection: str, scroll_filter: models.Filter, payload: list[str]
) -> Iterable[tuple[Any, dict[str, Any]]]:
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=_SCROLL,
            offset=offset,
            with_payload=payload,
            with_vectors=False,
        )
        for point in points:
            yield point.id, point.payload or {}
        if offset is None:
            return


def _passage(text: str) -> str:
    """The chunk without its breadcrumb line."""
    return text.split("\n\n", 1)[-1]


def place_document(
    qdrant: Any, collection: str, parent: str, pdfs: PdfSource, report: PageReport
) -> None:
    """Write the pages of one Drucksache's chunks."""
    points = sorted(
        _scroll(
            qdrant,
            collection,
            _drucksache_filter(
                models.FieldCondition(
                    key="source_parent_key", match=models.MatchValue(value=parent)
                )
            ),
            _PAYLOAD,
        ),
        key=lambda p: int(p[1].get("chunk_index") or 0),
    )
    if not points:
        return
    url = (points[0][1].get("meta") or {}).get("pdf_url")
    pdf = pdfs.pdf(url) if url else None
    if pdf is None:
        report.no_pdf.append(parent)
        return
    pages = passage_pages([_passage(str(p.get("text") or "")) for _, p in points], pdf)
    groups: dict[tuple[int, Optional[int]], list[Any]] = {}
    for (point_id, payload), (start, end) in zip(points, pages):
        if start is not None:
            groups.setdefault((start, end), []).append(point_id)
            payload = {
                **payload,
                "meta": {
                    **(payload.get("meta") or {}),
                    "page_start": start,
                    **({"page_end": end} if end else {}),
                },
            }
        report.count(payload)
    for (start, end), ids in groups.items():
        qdrant.set_payload(
            collection_name=collection,
            payload={"page_start": start, **({"page_end": end} if end else {})},
            points=models.PointIdsList(points=ids),
            key="meta",
            wait=True,
        )
    report.documents += 1


def backfill_chunks(
    qdrant: Any,
    collection: str,
    pdfs: PdfSource,
    *,
    limit: Optional[int] = None,
    report: Optional[PageReport] = None,
) -> PageReport:
    report = report or PageReport()
    parents = sorted(
        (
            f"{SourceType.DRUCKSACHE.value}:BT:{number}"
            for number in stored_drucksachen(qdrant, collection)
        ),
        key=_spread,
    )
    done = _placed(qdrant, collection)
    todo = [p for p in parents if p not in done][:limit]
    logger.info(
        "%d of %d Drucksachen placed, %d to place now",
        len(done & set(parents)),
        len(parents),
        len(todo),
    )
    for n, parent in enumerate(todo, 1):
        place_document(qdrant, collection, parent, pdfs, report)
        if n % 50 == 0:
            logger.info(
                "%d/%d Drucksachen, %d PDFs fetched", n, len(todo), pdfs.fetched
            )
    return report


def backfill_stages(
    store: ProcedureStore, pdfs: PdfSource, report: Optional[PageReport] = None
) -> PageReport:
    """Fill in the stages' PDF pages where they are missing; writes only
    records whose stages changed."""
    report = report or PageReport()
    records = store.all()
    missing = [r for r in records.values() if any(s.pdf_page is None for s in r.stages)]
    placed = stage_pdf_pages(missing, pdfs)
    changed = [new for new in placed if new.stages != records[new.vorgang_id].stages]
    store.set_stages(changed)
    report.records_written += len(changed)
    final = {**records, **{r.vorgang_id: r for r in placed}}
    for record in final.values():
        for stage in record.stages:
            if stage.document_kind == "Plenarprotokoll":
                report.stages += 1
                report.stages_placed += stage.pdf_page is not None
    return report


def stored_report(qdrant: Any, collection: str) -> PageReport:
    """The match rate over every stored Drucksache chunk."""
    report = PageReport()
    for _, payload in _scroll(
        qdrant, collection, _drucksache_filter(), ["meta", "doc_section"]
    ):
        report.count(payload)
    return report


def _guard_qdrant(url: str, allow_remote: bool) -> None:
    if (urlparse(url).hostname or "") not in _LOCAL_HOSTS and not allow_remote:
        raise SystemExit(
            f"Page backfill: QDRANT_URL={url} is not local; pass --allow-remote to write it."
        )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument(
        "--pdf-cache",
        type=Path,
        default=Path.home() / ".cache" / "wahlchat" / "dip-pdfs",
        help="where downloaded PDFs are kept",
    )
    parser.add_argument("--limit", type=int, help="place at most this many Drucksachen")
    parser.add_argument(
        "--no-stages", action="store_true", help="leave stages as they are"
    )
    parser.add_argument(
        "--no-chunks", action="store_true", help="leave chunks as they are"
    )
    parser.add_argument(
        "--report", action="store_true", help="print the stored match rate only"
    )
    parser.add_argument(
        "--interval", type=float, default=1.0, help="seconds between PDF downloads"
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="write a non-local Qdrant or a deployed Firestore",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    _guard_qdrant(url, args.allow_remote)
    qdrant = QdrantClient(
        url=url, api_key=os.getenv("QDRANT_API_KEY") or None, timeout=120
    )
    if args.report:
        print(stored_report(qdrant, args.collection).render())
        return 0

    pdfs = PdfSource(args.pdf_cache, min_interval=args.interval)
    report = PageReport()
    if not args.no_chunks:
        backfill_chunks(qdrant, args.collection, pdfs, limit=args.limit, report=report)
    if not args.no_stages:
        guard_firestore_target("Page backfill", allow_remote=args.allow_remote)
        from ingestion.firestore_client import firestore_client  # noqa: PLC0415 (after the guard)

        backfill_stages(ProcedureStore(firestore_client()), pdfs, report=report)
    print(report.render())
    return 0


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.exit(exit_code)
