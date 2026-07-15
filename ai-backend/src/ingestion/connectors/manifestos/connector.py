# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
ManifestoConnector — synchronous single-pass connector for party manifestos.

Implements the 3-method synchronous ABC (discover/fetch/normalize) and produces
list[ChunkRecord] directly from normalize() — the runner (run.py) owns embed +
upsert.  The cursor (since) is derived by the runner from Qdrant max(external_id)
for "party_manifesto" and passed to discover().

Source: the Abgeordnetenwatch ``election-program`` API (reuses ``AWClient``).

Source rule (locked design):
  1. If ``link[0].uri`` is non-null  -> scrape HTML main content (trafilatura).
  2. Elif ``file`` (PDF url) non-null -> download + parse the PDF in-memory.
  3. Else skip the program.

In both cases citation_url is the original source URL — wahl.chat does not
re-serve or store the files (no local storage, no Firestore source-doc).

Scope: programs whose parliament_period ``election_date`` >= 2020-01-01.

This module also exposes the shared I/O helpers (``_fetch_period_date``,
``determine_source``, ``load_program_pages``) used by both this connector and the
bespoke bulk CLI (bulk.py) so there is a single fetch/parse implementation.
"""

from __future__ import annotations

import logging
import os
from datetime import date as date_type
from typing import TYPE_CHECKING, Optional

from src.ingestion.connector import BaseConnector

if TYPE_CHECKING:
    from qdrant_client import QdrantClient
from src.ingestion.connectors.abgeordnetenwatch.client import AWClient
from src.ingestion.connectors.manifestos.mappers.corpus import (
    build_manifesto_records,
    chunk_pages,
    extract_main_text,
)
from src.ingestion.schemas import ChunkRecord, SourceType

logger = logging.getLogger(__name__)

# Programs older than this election_date are out of scope.
_CUTOFF = date_type.fromisoformat("2020-01-01")


# =============================================================================
# SHARED I/O HELPERS (used by this connector and bulk.py)
# =============================================================================


def _fetch_period_date(
    client: AWClient,
    period_id: int,
    cache: dict[int, Optional[str]],
) -> Optional[str]:
    """Resolve election_date for a parliament-period, caching by id.

    Args:
        client:    Initialised AWClient.
        period_id: AW parliament-period integer id.
        cache:     Mutable dict used to cache resolved dates (value may be None
                   when the period could not be resolved).

    Returns:
        ISO date string (``election_date`` or ``start_date_period``), or None.
    """
    if period_id in cache:
        return cache[period_id]
    try:
        resp = client.get(f"parliament-periods/{period_id}")
        data = resp.get("data") or {}
        date_str: Optional[str] = data.get("election_date") or data.get("start_date_period") or None
        cache[period_id] = date_str
        return date_str
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not resolve parliament-period %s: %s", period_id, exc)
        cache[period_id] = None
        return None


def determine_source(program: dict) -> tuple[str, str]:
    """Resolve (source_kind, source_url) for an election-program record.

    Applies the locked source rule: a non-null first ``link`` URI wins (HTML
    scrape); otherwise a non-null ``file`` (PDF download).

    Args:
        program: AW election-program dict.

    Returns:
        ("link", uri) or ("pdf", file_url).

    Raises:
        ValueError: If the program has neither a usable link nor a file.
    """
    links = program.get("link") or []
    link_uri: Optional[str] = None
    if links and isinstance(links, list):
        first = links[0]
        if isinstance(first, dict):
            link_uri = first.get("uri") or None

    file_url: Optional[str] = program.get("file") or None

    if link_uri:
        return "link", link_uri
    if file_url:
        return "pdf", file_url
    raise ValueError("no link or file")


def load_program_pages(source_kind: str, source_url: str) -> dict:
    """Download/scrape one program and return its page-annotated text (I/O).

    For ``link`` sources: GET the URI and extract the main article text via
    trafilatura (boilerplate-stripping, format-agnostic — see extract_main_text).
    For ``pdf`` sources: download the bytes and extract per-page text via pypdf.

    Nothing is persisted to disk: the PDF is parsed in-memory and discarded.
    Citations resolve to the original source URL, so wahl.chat never re-serves
    the file.

    Args:
        source_kind: ``"link"`` or ``"pdf"``.
        source_url:  The link URI or PDF download URL.

    Returns:
        Dict with keys ``pages`` (list[(page_no, text)]) and ``total_pages``
        (int for pdf, None for link).

    Raises:
        ValueError: On any skip/failure (HTML too short, HTML fetch failed,
                    PDF download failed, PDF parse failed) — the message is
                    suitable for a "SKIP program ...: {msg}" log line.
    """
    import requests as _requests  # noqa: PLC0415

    if source_kind == "link":
        try:
            resp = _requests.get(
                source_url,
                timeout=60,
                headers={"User-Agent": "wahl.chat-ingest"},
            )
            resp.raise_for_status()
            text_content = extract_main_text(resp.text)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"HTML fetch failed: {exc}") from exc
        if len(text_content) < 500:
            raise ValueError(f"HTML too short ({len(text_content)} chars)")
        return {"pages": [(1, text_content)], "total_pages": None}

    # source_kind == "pdf"
    from io import BytesIO  # noqa: PLC0415

    import pypdf  # noqa: PLC0415

    try:
        pdf_resp = _requests.get(
            source_url,
            timeout=60,
            headers={"User-Agent": "wahl.chat-ingest"},
        )
        pdf_resp.raise_for_status()
        pdf_bytes = pdf_resp.content
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"PDF download failed: {exc}") from exc

    try:
        reader = pypdf.PdfReader(BytesIO(pdf_bytes))
        total_pages = len(reader.pages)
        pages_list: list[tuple[int, str]] = []
        for page_no, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            pages_list.append((page_no, page_text))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"PDF parse failed: {exc}") from exc

    return {"pages": pages_list, "total_pages": total_pages}


# =============================================================================
# ManifestoConnector
# =============================================================================


class ManifestoConnector(BaseConnector):
    """Connector for AW election-program records → party_manifesto ChunkRecords.

    Synchronous single-pass connector:
        discover(since) → fetch → normalize → [runner embeds + upserts]

    The cursor (since) is the max external_id (raw integer AW program_id) already
    committed to Qdrant for "party_manifesto", derived by the runner via
    get_cursor().  No Firestore and no bespoke flags on this path — those live in
    bulk.py.  discover() caches the program records and resolved election dates as
    per-run instance state so fetch() needs no second discovery pass.

    """

    # Class attribute: used by runner.get_cursor() to scope the Qdrant scroll.
    source_type: str = SourceType.PARTY_MANIFESTO.value

    def __init__(self) -> None:
        self._client = AWClient()

        # Per-run caches populated by discover() and read by fetch().
        self._period_date_cache: dict[int, Optional[str]] = {}
        self._programs: dict[int, dict] = {}
        self._period_dates: dict[int, str] = {}

        # Lazy Qdrant client for set-difference discovery.
        # Initialised on first call to _get_qdrant().
        self._qdrant: Optional[QdrantClient] = None

    # ------------------------------------------------------------------
    # 1a. Qdrant lazy singleton (set-difference discovery)
    # ------------------------------------------------------------------

    def _get_qdrant(self) -> QdrantClient:
        """Return the per-instance Qdrant client, initializing on first call.

        Mirrors the AW connector's lazy singleton. Kept as an instance method so
        tests can monkeypatch it (or _get_ingested_program_ids) per-connector.
        """
        if self._qdrant is None:
            from qdrant_client import QdrantClient  # noqa: PLC0415

            self._qdrant = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                api_key=os.getenv("QDRANT_API_KEY"),
            )
        return self._qdrant

    def _get_ingested_program_ids(self) -> set[int]:
        """Return the set of AW program ids already ingested as party_manifesto.

        Scrolls all party_manifesto chunks and collects their external_id (= AW
        program id). Used for set-difference discovery.

        This replaces the max(external_id) high-water mark, which permanently lost
        any program that was skipped/failed below the max on a prior run (the max
        advanced past it and the strict ``pid <= since`` filter never re-surfaced
        it). Set-difference is gap-free and self-healing: a program missing from
        Qdrant is always re-attempted, and a permanently-unprocessable program
        simply stays absent without blocking newer programs. It also removes the
        manifesto batch-window stall (already-present programs no longer occupy
        the discover window).
        """
        from qdrant_client import models as qdrant_models  # noqa: PLC0415
        from src.ingestion.setup_collection import COLLECTION_NAME  # noqa: PLC0415

        qdrant = self._get_qdrant()
        ingested: set[int] = set()
        next_offset: Optional[qdrant_models.ExtendedPointId] = None
        scroll_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="source_type",
                    match=qdrant_models.MatchValue(value=self.source_type),
                )
            ]
        )
        while True:
            points, next_offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=1000,
                offset=next_offset,
                with_payload=["external_id"],
                with_vectors=False,
            )
            for p in points:
                ext = p.payload.get("external_id") if p.payload else None
                if isinstance(ext, int):
                    ingested.add(ext)
            if next_offset is None:
                break
        return ingested

    # ------------------------------------------------------------------
    # 1b. discover — 2020 floor + set-difference vs Qdrant, ascending by program_id
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return election-program ids to process, oldest first.

        Fetches all election-program records, resolves each program's
        parliament-period election_date (cached), keeps those >= 2020-01-01, and
        includes a program only when its id is NOT yet present in Qdrant
        (set-difference — mirrors the AW votes connector). Caches the program
        records + resolved dates so fetch() needs no re-discovery.

        The global ``since`` argument from run_connector() is accepted (preserves
        the ABC contract) but IGNORED — a max-external_id watermark permanently
        dropped any program that transiently failed below the max; set-difference
        is gap-free and always retries missing programs.

        MANIFESTO_REFRESH=1 (same 1/true/yes parsing as the votes connector's
        AW_REFRESH) forces a full reconcile: the already-ingested exclusion is
        skipped so run.py's content-hash rewrite + orphan cleanup can propagate
        replaced/corrected PDFs and shrunk programs (E1). Unchanged chunks are
        cheaply skipped there without re-embedding.

        Args:
            since: Max external_id (AW program integer ID) already committed to
                   Qdrant for "party_manifesto". Accepted for ABC-contract
                   compatibility but not used (set-difference supersedes it).

        Returns:
            List of program id strings sorted ascending by program_id.
        """
        self._programs = {}
        self._period_dates = {}

        all_programs = self._client.get_all("election-program", {})

        # E1: MANIFESTO_REFRESH skips the ingested-ids exclusion so already
        # present programs flow through run.py's content-hash guard again.
        refresh = os.getenv("MANIFESTO_REFRESH", "").strip().lower() in ("1", "true", "yes")
        ingested_ids: set[int] = set() if refresh else self._get_ingested_program_ids()

        eligible: list[int] = []
        for program in all_programs:
            pid = program.get("id")
            if not isinstance(pid, int):
                continue
            period_obj = program.get("parliament_period") or {}
            period_id = period_obj.get("id")
            if not period_id:
                continue
            date_iso = _fetch_period_date(self._client, int(period_id), self._period_date_cache)
            if not date_iso:
                continue
            try:
                election_date = date_type.fromisoformat(date_iso)
            except (ValueError, TypeError):
                continue
            if election_date < _CUTOFF:
                continue
            if pid in ingested_ids:
                continue
            self._programs[pid] = program
            self._period_dates[pid] = date_iso
            eligible.append(pid)

        eligible.sort()
        return [str(pid) for pid in eligible]

    # ------------------------------------------------------------------
    # 2. fetch — download/scrape one program; never raises (defers to normalize)
    # ------------------------------------------------------------------

    def fetch(self, external_id: str) -> dict:
        """Fetch raw page text + provenance for a single program id.

        Reads the program record + election_date from the discover() cache, then
        downloads/scrapes its content.  Any skip/failure is captured as a
        ``skip_reason`` in the returned dict (never raised) so the runner — which
        does not wrap fetch() — proceeds to normalize(), where the skip surfaces
        as a ValueError and run_connector skip-and-continues.

        Args:
            external_id: String program id (e.g. "598").

        Returns:
            Dict with ``program``, ``period_date_iso``, ``source_kind``,
            ``source_url``, ``pages``, ``total_pages`` — or a minimal dict
            carrying ``skip_reason`` on any problem. Nothing is persisted to
            disk (no stored_path — PDFs are parsed in-memory and discarded).
        """
        pid = int(external_id)
        program = self._programs.get(pid)
        period_date_iso = self._period_dates.get(pid)

        if program is None:
            return {"program": None, "skip_reason": f"program {pid} not in discover cache"}

        try:
            source_kind, source_url = determine_source(program)
            content = load_program_pages(source_kind, source_url)
        except ValueError as exc:
            return {"program": program, "period_date_iso": period_date_iso, "skip_reason": str(exc)}

        return {
            "program": program,
            "period_date_iso": period_date_iso,
            "source_kind": source_kind,
            "source_url": source_url,
            **content,
        }

    # ------------------------------------------------------------------
    # 3. normalize — chunk + build ChunkRecords
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords from a fetched program payload.

        Args:
            raw: Dict returned by fetch().

        Returns:
            list[ChunkRecord], one per chunk.

        Raises:
            ValueError: If fetch() flagged a skip, the election_date is missing,
                        or the program produces no text/records (run_connector
                        skip-and-continues).
        """
        skip_reason = raw.get("skip_reason")
        if skip_reason:
            raise ValueError(skip_reason)

        program: dict = raw["program"]
        period_date_iso: Optional[str] = raw.get("period_date_iso")
        if not period_date_iso:
            raise ValueError(f"program {program.get('id')} has no resolvable election_date")

        source_kind: str = raw["source_kind"]
        chunk_tuples = chunk_pages(raw["pages"])
        if not chunk_tuples:
            raise ValueError(f"program {program.get('id')} produced no text after chunking")

        # HTML sources carry no page numbers per spec.
        if source_kind == "link":
            build_chunks: list[tuple[str, Optional[int], Optional[int]]] = [
                (text, None, None) for text, _ps, _pe in chunk_tuples
            ]
        else:
            build_chunks = list(chunk_tuples)

        records = build_manifesto_records(
            program=program,
            period_date_iso=period_date_iso,
            chunks=build_chunks,
            source_kind=source_kind,
            source_url=raw["source_url"],
            total_pages=raw.get("total_pages"),
        )
        if not records:
            raise ValueError(f"program {program.get('id')} produced no records")
        return records
