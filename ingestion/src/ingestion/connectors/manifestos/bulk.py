# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Standalone bulk CLI for ingesting party manifestos (Wahlprogramme) from the
Abgeordnetenwatch ``election-program`` API into ``wahlchat_chunks_{ENV}``.

This is the bespoke local-dev entrypoint that the generic runner (run.py) cannot
express: it adds the --dry-run / --ids / --limit flags on top of the same data
path as ManifestoConnector.  The connector's interface methods are driven by
run.py for the standard cursor-based embed path; this script reuses the
connector's shared I/O helpers (determine_source, load_program_pages,
_fetch_period_date) and the pure mappers so there is a single fetch/parse +
record-build implementation.

Source rule (locked design, with fallback):
  1. If ``link[0].uri`` is non-null  -> scrape HTML main content (trafilatura).
  2. If that fails or no link exists, and ``file`` (PDF url) is non-null ->
     download + parse the PDF in-memory.
  3. Only when every candidate fails is the program skipped.

citation_url points at the original source URL in both cases — wahl.chat does
not re-serve or store the files (no local storage, no Firestore source-doc).

Scope: by default ALL programs are ingested. Pass ``--since YYYY-MM-DD`` (or set
``MANIFESTO_SINCE``) to floor by parliament_period ``election_date``; the operator
chooses the window and the CLI carries no built-in cut-off.

Usage (local dev):
    cd ingestion
    uv run python -m ingestion.connectors.manifestos.bulk --dry-run --limit 5
    uv run python -m ingestion.connectors.manifestos.bulk --ids 598,599,600
    uv run python -m ingestion.connectors.manifestos.bulk --since 2020-01-01
    QDRANT_URL=http://localhost:6333 ENV=dev uv run python -m ingestion.connectors.manifestos.bulk

Re-running REWRITES each processed program's footprint replacement-safely:
embed → upsert the fresh chunks (deterministic point IDs overwrite in place,
wait=True) → only THEN delete orphaned point ids the new output no longer
produces. The old footprint is never removed before its replacement is
durable, so a Qdrant failure mid-flush cannot leave a program absent.
Everything flushed IS re-embedded (this bespoke CLI has no content-hash skip —
use run.py + MANIFESTO_REFRESH for the cheap reconcile).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date as date_type
from pathlib import Path
from typing import Optional

# CLI startup ONLY: load ingestion/.env BEFORE the imports below — embeddings
# and setup_collection freeze EMBEDDING_MODEL / EMBEDDING_DIM / COLLECTION_NAME
# from the environment at import time, so a later load_dotenv() configures
# nothing. override=False keeps explicitly-exported shell env (QDRANT_URL,
# ENV, …) authoritative — a `make run-manifestos QDRANT_URL=… ENV=prod`
# invocation must never be silently redirected to the local .env store.
if __name__ == "__main__":
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[4] / ".env"

    # Fall back to ai-backend/.env so setups that keep every key in one
    # file keep working after the ingestion split.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient

from ingestion.connectors.manifestos.connector import (
    _fetch_period_date,
    determine_source_candidates,
    load_program_pages,
    resolve_since_floor,
)
from ingestion.connectors.manifestos.mappers.corpus import (
    SourceKind,
    build_manifesto_records,
    chunk_pages,
    party_to_slug,
)
from ingestion.embeddings import get_embeddings
from ingestion.ids import compute_chunk_id
from ingestion.run import _embed_texts, _upsert_chunks
from ingestion.schemas import ChunkRecord
from ingestion.setup_collection import COLLECTION_NAME, check_fingerprint

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100  # chunks per embed+upsert batch


# =============================================================================
# MAIN INGEST LOOP
# =============================================================================


def ingest(
    qdrant: QdrantClient,
    embed: Embeddings,
    limit: Optional[int] = None,
    ids: Optional[list[int]] = None,
    dry_run: bool = False,
    since: Optional[date_type] = None,
) -> tuple[int, int]:
    """Fetch manifesto programs from AW, embed, and upsert into Qdrant.

    Args:
        qdrant:  Initialised QdrantClient.
        embed:   Initialised embeddings client (from get_embeddings()).
        limit:   Max programs to process (None = all passing the date filter).
        ids:     Specific AW program IDs to process (overrides limit).
        dry_run: If True, skip embed/upsert; fetch, parse, and print per-program
                 stats (party, period, source_kind, pages, chars, chunks).
        since:   Optional election-date floor; programs whose parliament_period
                 election_date is strictly before it are skipped. When None
                 (default) NO floor is applied and every program is in scope.

    Returns:
        Tuple of (programs_processed, chunks_upserted).
    """
    from ingestion.connectors.abgeordnetenwatch.client import AWClient  # noqa: PLC0415

    client = AWClient()
    period_date_cache: dict[int, Optional[str]] = {}

    print("Discovering election-program records from AW API ...")
    all_programs: list[dict] = client.get_all("election-program", {})
    print(f"  Found {len(all_programs)} total programs")

    # Filter to requested IDs if specified
    if ids:
        id_set = set(ids)
        all_programs = [p for p in all_programs if p.get("id") in id_set]
        print(f"  After --ids filter: {len(all_programs)} programs")

    # Resolve election_date per program and apply the optional floor. With no
    # floor (since is None) every program is kept — the CLI has no built-in cut-off.
    eligible_programs: list[tuple[dict, str]] = []  # (program, date_iso)

    for program in all_programs:
        period_obj = program.get("parliament_period") or {}
        period_id = period_obj.get("id")
        if not period_id:
            continue
        date_iso = _fetch_period_date(client, int(period_id), period_date_cache)
        if not date_iso:
            continue
        try:
            election_date = date_type.fromisoformat(date_iso)
        except (ValueError, TypeError):
            continue
        if since is not None and election_date < since:
            continue
        eligible_programs.append((program, date_iso))

    _floor_label = f">= {since.isoformat()}" if since is not None else "no floor"
    print(f"  After date filter ({_floor_label}): {len(eligible_programs)} programs")

    if limit is not None and not ids:
        eligible_programs = eligible_programs[:limit]
        print(f"  After --limit {limit}: {len(eligible_programs)} programs")

    programs_processed = 0
    chunks_total = 0
    batch: list[ChunkRecord] = []

    def _flush(b: list[ChunkRecord]) -> int:
        if not b or dry_run:
            return 0
        from qdrant_client import models as qdrant_models  # noqa: PLC0415

        # Replacement-safe commit order — the program must never be absent:
        #   1. EMBED first (the failure-prone external call; the old footprint
        #      stays intact if it fails).
        #   2. UPSERT the fresh chunks (deterministic point IDs overwrite the
        #      surviving ids in place, wait=True). A 317-chunk program spans
        #      multiple upsert requests; even if a later slice fails, nothing
        #      has been deleted yet.
        #   3. Only after ALL writes succeeded: delete the orphaned point ids
        #      (stored footprint minus the new output) so a shrunk/replaced
        #      PDF leaves no stale higher-index chunks behind.
        vectors = _embed_texts(embed, [c.text for c in b])

        new_ids_by_siid: dict[str, set[str]] = {}
        for c in b:
            new_ids_by_siid.setdefault(str(c.source_item_id), set()).add(
                str(compute_chunk_id(c.source_item_id, c.chunk_index))
            )

        _upsert_chunks(qdrant, COLLECTION_NAME, b, vectors)

        orphans: list[str] = []
        scroll_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="source_item_id",
                    match=qdrant_models.MatchAny(any=sorted(new_ids_by_siid)),
                )
            ]
        )
        next_offset = None
        while True:
            points, next_offset = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=1000,
                offset=next_offset,
                with_payload=["source_item_id"],
                with_vectors=False,
            )
            for p in points:
                siid = str((p.payload or {}).get("source_item_id"))
                if str(p.id) not in new_ids_by_siid.get(siid, set()):
                    orphans.append(str(p.id))
            if next_offset is None:
                break
        if orphans:
            qdrant.delete(
                collection_name=COLLECTION_NAME,
                points_selector=qdrant_models.PointIdsList(points=sorted(orphans)),
                wait=True,
            )
        return len(b)

    for program, period_date_iso in eligible_programs:
        program_id: int = program["id"]
        party_label: str = (program.get("party") or {}).get("label") or ""
        period_label: str = (program.get("parliament_period") or {}).get("label") or ""

        # Ordered source candidates (locked source rule with PDF fallback).
        try:
            candidates = determine_source_candidates(program)
        except ValueError:
            print(f"  SKIP program {program_id} ({party_label}): no link or file")
            continue

        party_slug = party_to_slug(party_label)

        # --- Fetch and parse (first working candidate wins) ---
        content: Optional[dict] = None
        source_kind: SourceKind = candidates[0][0]
        source_url: str = candidates[0][1]
        failures: list[str] = []
        for source_kind, source_url in candidates:
            try:
                content = load_program_pages(source_kind, source_url)
                break
            except ValueError as exc:
                failures.append(f"{source_kind}: {exc}")
        if content is None:
            print(
                f"  SKIP program {program_id} ({party_label}): " + "; ".join(failures)
            )
            continue

        pages_list: list[tuple[int, str]] = content["pages"]
        total_pages: Optional[int] = content["total_pages"]

        # --- Chunk ---
        chunk_tuples = chunk_pages(pages_list)
        if not chunk_tuples:
            print(
                f"  SKIP program {program_id} ({party_label}): no text after chunking"
            )
            continue

        # Convert chunk_pages output to the format expected by build_manifesto_records.
        # For HTML source, null out page numbers per spec.
        if source_kind == SourceKind.LINK:
            build_chunks: list[tuple[str, Optional[int], Optional[int]]] = [
                (text, None, None) for text, _ps, _pe in chunk_tuples
            ]
        else:
            build_chunks = list(chunk_tuples)

        # --- Count characters for dry-run report (chunking is character-based) ---
        total_chars = sum(len(t) for t, _, _ in build_chunks)

        if dry_run:
            print(
                f"  DRY-RUN program {program_id}: party={party_slug!r} "
                f"period={period_label!r} source_kind={source_kind!r} "
                f"pages={total_pages} chars={total_chars} chunks={len(build_chunks)}"
            )
            programs_processed += 1
            chunks_total += len(build_chunks)
            continue

        # --- Build records ---
        records = build_manifesto_records(
            program=program,
            period_date_iso=period_date_iso,
            chunks=build_chunks,
            source_kind=source_kind,
            source_url=source_url,
            total_pages=total_pages,
        )

        if not records:
            print(f"  SKIP program {program_id} ({party_label}): no records built")
            continue

        # --- Batch embed + upsert ---
        batch.extend(records)
        chunks_total += len(records)
        print(
            f"  program {program_id}: party={party_slug!r} "
            f"period={period_label!r} source={source_kind} chunks={len(records)}"
        )

        if len(batch) >= _BATCH_SIZE:
            _flush(batch)
            batch = []

        programs_processed += 1

    # Flush remaining
    _flush(batch)

    return programs_processed, chunks_total


# =============================================================================
# __main__ entrypoint
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description=(
            "Ingest party manifestos from the Abgeordnetenwatch election-program API "
            "into the Qdrant wahlchat_chunks_{ENV} collection."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N programs passing the 2020 filter.",
    )
    parser.add_argument(
        "--ids",
        type=str,
        default=None,
        metavar="ID1,ID2,...",
        help="Comma-separated AW election-program IDs to process (for smoke testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Fetch and parse programs but skip embed + upsert. "
            "Prints per-program stats (party, period, source_kind, pages, chars, chunks)."
        ),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Only ingest programs whose parliament_period election_date is on or "
            "after this ISO date. Overrides MANIFESTO_SINCE. Default: no floor "
            "(ingest all)."
        ),
    )
    args = parser.parse_args()

    # --since wins over MANIFESTO_SINCE; both default to no floor. An invalid
    # value raises here (loud misconfiguration) before any AW/OpenAI work.
    try:
        since_floor = resolve_since_floor(args.since)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    specific_ids: Optional[list[int]] = None
    if args.ids:
        try:
            specific_ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
        except ValueError:
            print(
                "ERROR: --ids must be a comma-separated list of integers",
                file=sys.stderr,
            )
            sys.exit(1)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    _qdrant = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))
    # Corpus passages → RETRIEVAL_DOCUMENT (matches the ingestion runner + the
    # RETRIEVAL_QUERY side in retrieve.py; ignored for OpenAI).
    _embed = get_embeddings(task_type="RETRIEVAL_DOCUMENT")
    # Refuse to write into a collection whose fingerprint contradicts the
    # current provider/model configuration (skipped on --dry-run: no writes).
    if not args.dry_run:
        check_fingerprint(_qdrant, COLLECTION_NAME)

    print(
        f"Ingesting manifestos (dry_run={args.dry_run}, "
        f"limit={args.limit}, ids={specific_ids}, "
        f"since={since_floor.isoformat() if since_floor else None}) ..."
    )
    try:
        processed, chunks = ingest(
            _qdrant,
            _embed,
            limit=args.limit,
            ids=specific_ids,
            dry_run=args.dry_run,
            since=since_floor,
        )
    except Exception:  # noqa: BLE001
        import traceback  # noqa: PLC0415

        print("ERROR: ingest failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    print(f"Done. programs_processed={processed}  chunks_upserted={chunks}")
