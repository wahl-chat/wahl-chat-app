# SPDX-FileCopyrightText: 2025 wahl.chat
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

Source rule (locked design):
  1. If ``link[0].uri`` is non-null  -> scrape HTML main content (trafilatura).
  2. Elif ``file`` (PDF url) non-null -> download + parse the PDF in-memory.
  3. Else skip the program.

citation_url points at the original source URL in both cases — wahl.chat does
not re-serve or store the files (no local storage, no Firestore source-doc).

Scope: programs whose parliament_period ``election_date`` >= 2020-01-01.

Usage (local dev):
    cd ai-backend
    uv run python -m src.ingestion.connectors.manifestos.bulk --dry-run --limit 5
    uv run python -m src.ingestion.connectors.manifestos.bulk --ids 598,599,600
    QDRANT_URL=http://localhost:6333 ENV=dev uv run python -m src.ingestion.connectors.manifestos.bulk

Re-running REWRITES each processed program's footprint: the flush deletes the
program's existing chunks by source_item_id (wait=True) before upserting the
fresh ones, so a shrunk/replaced PDF leaves no stale higher-index chunks behind.
Deterministic chunk UUIDs (via compute_chunk_id) keep unchanged chunks at the
same point IDs; everything flushed IS re-embedded (this bespoke CLI has no
content-hash skip — use run.py + MANIFESTO_REFRESH for the cheap reconcile).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date as date_type
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from src.ingestion.connectors.manifestos.connector import (
    _fetch_period_date,
    determine_source,
    load_program_pages,
)
from src.ingestion.connectors.manifestos.mappers.corpus import (
    build_manifesto_records,
    chunk_pages,
    party_to_slug,
)
from src.ingestion.run import _embed_texts, _upsert_chunks
from src.ingestion.schemas import ChunkRecord
from src.ingestion.setup_collection import COLLECTION_NAME, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100  # chunks per embed+upsert batch


# =============================================================================
# MAIN INGEST LOOP
# =============================================================================


def ingest(
    qdrant: QdrantClient,
    embed: OpenAIEmbeddings,
    limit: Optional[int] = None,
    ids: Optional[list[int]] = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Fetch manifesto programs from AW, embed, and upsert into Qdrant.

    Args:
        qdrant:  Initialised QdrantClient.
        embed:   Initialised OpenAIEmbeddings instance.
        limit:   Max programs to process (None = all passing the 2020 filter).
        ids:     Specific AW program IDs to process (overrides limit).
        dry_run: If True, skip embed/upsert; fetch, parse, and print per-program
                 stats (party, period, source_kind, pages, chars, chunks).

    Returns:
        Tuple of (programs_processed, chunks_upserted).
    """
    from src.ingestion.connectors.abgeordnetenwatch.client import AWClient  # noqa: PLC0415

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

    # Resolve election_date per program and filter to >= 2020-01-01
    cutoff = date_type.fromisoformat("2020-01-01")
    programs_2020: list[tuple[dict, str]] = []  # (program, date_iso)

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
        if election_date >= cutoff:
            programs_2020.append((program, date_iso))

    print(f"  After 2020 filter: {len(programs_2020)} programs")

    if limit is not None and not ids:
        programs_2020 = programs_2020[:limit]
        print(f"  After --limit {limit}: {len(programs_2020)} programs")

    programs_processed = 0
    chunks_total = 0
    batch: list[ChunkRecord] = []

    def _flush(b: list[ChunkRecord]) -> int:
        if not b or dry_run:
            return 0
        from qdrant_client import models as qdrant_models  # noqa: PLC0415

        # Embed FIRST — an embed failure leaves the existing footprint intact
        # (no delete-before-embed loss window; mirrors run.py's ordering).
        vectors = _embed_texts(embed, [c.text for c in b])

        # Rewrite semantics (mirrors run.py's footprint guard) — delete each
        # program's EXISTING footprint by source_item_id before upserting, one
        # delete per program with wait=True, so a re-run against a shrunk PDF
        # (fewer chunks than stored) leaves no stale higher-index chunks
        # retrievable forever.
        siids = sorted({str(c.source_item_id) for c in b})
        for siid in siids:
            qdrant.delete(
                collection_name=COLLECTION_NAME,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="source_item_id",
                                match=qdrant_models.MatchValue(value=siid),
                            )
                        ]
                    )
                ),
                wait=True,
            )

        _upsert_chunks(qdrant, COLLECTION_NAME, b, vectors)
        return len(b)

    for program, period_date_iso in programs_2020:
        program_id: int = program["id"]
        party_label: str = (program.get("party") or {}).get("label") or ""
        period_label: str = (program.get("parliament_period") or {}).get("label") or ""

        # Determine source_kind / source_url (locked source rule)
        try:
            source_kind, source_url = determine_source(program)
        except ValueError:
            print(f"  SKIP program {program_id} ({party_label}): no link or file")
            continue

        party_slug = party_to_slug(party_label)

        # --- Fetch and parse ---
        try:
            content = load_program_pages(source_kind, source_url)
        except ValueError as exc:
            print(f"  SKIP program {program_id} ({party_label}): {exc}")
            continue

        pages_list: list[tuple[int, str]] = content["pages"]
        total_pages: Optional[int] = content["total_pages"]

        # --- Chunk ---
        chunk_tuples = chunk_pages(pages_list)
        if not chunk_tuples:
            print(f"  SKIP program {program_id} ({party_label}): no text after chunking")
            continue

        # Convert chunk_pages output to the format expected by build_manifesto_records.
        # For HTML source, null out page numbers per spec.
        if source_kind == "link":
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
    # Load ai-backend/.env if present.
    from pathlib import Path  # noqa: PLC0415

    from dotenv import load_dotenv  # noqa: PLC0415

    _env_path = Path(__file__).resolve().parents[4] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

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
    args = parser.parse_args()

    specific_ids: Optional[list[int]] = None
    if args.ids:
        try:
            specific_ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
        except ValueError:
            print("ERROR: --ids must be a comma-separated list of integers", file=sys.stderr)
            sys.exit(1)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    _qdrant = QdrantClient(url=qdrant_url)
    _embed = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    print(
        f"Ingesting manifestos (dry_run={args.dry_run}, "
        f"limit={args.limit}, ids={specific_ids}) ..."
    )
    try:
        processed, chunks = ingest(
            _qdrant,
            _embed,
            limit=args.limit,
            ids=specific_ids,
            dry_run=args.dry_run,
        )
    except Exception:  # noqa: BLE001
        import traceback  # noqa: PLC0415

        print("ERROR: ingest failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    print(f"Done. programs_processed={processed}  chunks_upserted={chunks}")
