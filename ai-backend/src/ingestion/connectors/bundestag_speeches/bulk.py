# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Standalone bulk CLI for replaying Bundestag plenary speeches from a local
JSONL dump into ``wahlchat_chunks_{ENV}`` via the relocated corpus mapper.

This is the --from-jsonl backfill entrypoint that keeps the existing 99 MB
``speeches.jsonl`` replayable without re-fetching from the DIP API.  The
live connector (``connector.py``) handles incremental runs via ``run.py``
and the YYYYMMDD cursor; this script handles the one-shot historical backfill.

Design notes:
  - This is the ONLY file within the ``bundestag_speeches`` package permitted
    to call the runner ``_embed_texts`` / ``_upsert_chunks`` helpers directly.
    The connector never touches those helpers — ``run.py`` owns that path.
  - Replayed rows pre-date the live connector, so ``build_chunk_records``
    leaves ``external_id=None`` for the bulk path (the live connector stamps
    YYYYMMDD in ``normalize()``; a future migration patches legacy rows).
  - The script is idempotent: deterministic chunk UUIDs (via ``compute_chunk_id``)
    mean re-running upserts the same Qdrant point IDs, which is a no-op.

Usage (local dev):
    cd ai-backend
    uv run python -m src.ingestion.connectors.bundestag_speeches.bulk --help
    uv run python -m src.ingestion.connectors.bundestag_speeches.bulk --limit 20
    uv run python -m src.ingestion.connectors.bundestag_speeches.bulk speeches.jsonl
    QDRANT_URL=http://localhost:6333 ENV=dev \\
        uv run python -m src.ingestion.connectors.bundestag_speeches.bulk

JSONL path resolution (CLI arg > SPEECHES_JSONL env > repo-root default):
    1. Positional ``jsonl_path`` argument (also accepted as ``--from-jsonl``).
    2. ``SPEECHES_JSONL`` environment variable.
    3. Repo root ``speeches.jsonl`` (three levels above ``ai-backend/``).

Requires: make stores-up first (Qdrant running at QDRANT_URL).
          OPENAI_API_KEY in ai-backend/.env (auto-loaded if present).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from datetime import date as _date_type

from src.ingestion.connectors.bundestag_speeches.mappers.corpus import build_chunk_records
from src.ingestion.run import _embed_texts, _upsert_chunks
from src.ingestion.schemas import ChunkRecord
from src.ingestion.setup_collection import COLLECTION_NAME, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100  # chunks per embed+upsert batch


# =============================================================================
# MAIN INGEST LOOP
# =============================================================================


def ingest(
    jsonl_path: Path,
    qdrant: QdrantClient,
    embed: OpenAIEmbeddings,
    limit: Optional[int] = None,
) -> tuple[int, int]:
    """Read speeches from *jsonl_path* and upsert into Qdrant in batches.

    Each JSONL line is a speech dict passed through
    ``build_chunk_records`` from the relocated corpus mapper.  Replayed
    rows are stamped with ``external_id=YYYYMMDD`` so that
    ``get_cursor("parliamentary_speech")`` picks up the backfill and the
    first live incremental run does not re-embed everything.

    Args:
        jsonl_path:  Path to the speeches JSONL file (one JSON object per line).
        qdrant:      Initialised QdrantClient.
        embed:       Initialised OpenAIEmbeddings instance.
        limit:       Maximum number of speeches to process (None = all).

    Returns:
        Tuple of (speeches_processed, chunks_upserted).
    """
    speeches_processed = 0
    chunks_total = 0
    batch: list[ChunkRecord] = []

    def _flush(b: list[ChunkRecord]) -> int:
        if not b:
            return 0
        vectors = _embed_texts(embed, [c.text for c in b])
        _upsert_chunks(qdrant, COLLECTION_NAME, b, vectors)
        return len(b)

    with jsonl_path.open(encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            if limit is not None and speeches_processed >= limit:
                break

            speech = json.loads(raw_line)
            records = build_chunk_records(speech)
            if not records:
                # Skip empty-text or unparseable-date speeches (no chunk emitted, not counted).
                continue

            # Stamp external_id=YYYYMMDD on each bulk-backfill record.
            # build_chunk_records() leaves external_id=None for mapper neutrality.
            # Without stamping, run.py's get_cursor() ignores these points entirely
            # (exclude_none=True in _upsert_chunks drops the external_id key), so the
            # first live incremental run re-fetches and re-embeds everything.
            # Convention: same YYYYMMDD integer the live connector's normalize() uses.
            # On missing/unparseable date, build_chunk_records already returns [] above,
            # so raw_date here is always a valid ISO date string.
            raw_date = speech.get("date") or ""
            try:
                parsed = _date_type.fromisoformat(raw_date)
                yyyymmdd = int(parsed.strftime("%Y%m%d"))
                records = [c.model_copy(update={"external_id": yyyymmdd}) for c in records]
            except (ValueError, TypeError):
                # Defensive guard: build_chunk_records would have already skipped a bad
                # date, but guard here to be safe — skip without stamping.
                logger.warning(
                    "bulk.ingest: speech %r has unparseable date %r — skipping (no stamp).",
                    speech.get("id"),
                    raw_date,
                )
                continue

            speeches_processed += 1
            batch.extend(records)
            chunks_total += len(records)

            if len(batch) >= _BATCH_SIZE:
                flushed = _flush(batch)
                logger.info("Flushed batch of %d chunks (total so far: %d)", flushed, chunks_total)
                batch = []

    _flush(batch)

    return speeches_processed, chunks_total


# =============================================================================
# __main__ entrypoint
# =============================================================================

if __name__ == "__main__":
    # Load ai-backend/.env if present.
    # bulk.py sits at: ai-backend/src/ingestion/connectors/bundestag_speeches/bulk.py
    # parents[4] = ai-backend/ (same depth as manifestos/bulk.py)
    from dotenv import load_dotenv  # noqa: PLC0415

    _env_path = Path(__file__).resolve().parents[4] / ".env"
    if _env_path.exists():
        # .env is the source of truth for local dev — let it win over any stale
        # value inherited from the shell.
        load_dotenv(_env_path, override=True)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description=(
            "Replay Bundestag plenary speeches from a local JSONL dump into the "
            "Qdrant wahlchat_chunks_{ENV} collection via the relocated corpus mapper. "
            "No DIP API key required — reads from speeches.jsonl, not the live API."
        ),
    )
    parser.add_argument(
        "jsonl_path",
        nargs="?",
        default=None,
        metavar="JSONL_PATH",
        help=(
            "Path to speeches JSONL file. "
            "Falls back to SPEECHES_JSONL env var or repo-root speeches.jsonl. "
            "Also accepted as --from-jsonl."
        ),
    )
    parser.add_argument(
        "--from-jsonl",
        dest="from_jsonl",
        default=None,
        metavar="JSONL_PATH",
        help="Alias for the positional jsonl_path argument.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N speeches (for smoke testing).",
    )
    args = parser.parse_args()

    # Resolve JSONL path: positional arg > --from-jsonl > env var > repo-root default.
    raw_path = args.jsonl_path or args.from_jsonl
    if raw_path:
        resolved_path = Path(raw_path).resolve()
    elif os.getenv("SPEECHES_JSONL"):
        resolved_path = Path(os.environ["SPEECHES_JSONL"]).resolve()
    else:
        # Repo root is 5 levels above this file:
        # ai-backend/src/ingestion/connectors/bundestag_speeches/bulk.py → parents[5]
        resolved_path = Path(__file__).resolve().parents[5] / "speeches.jsonl"

    if not resolved_path.exists():
        print(f"ERROR: JSONL file not found: {resolved_path}", file=sys.stderr)
        sys.exit(1)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    _qdrant = QdrantClient(url=qdrant_url)
    _embed = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    print(f"Replaying speeches from {resolved_path} (limit={args.limit}) ...")
    try:
        processed, chunks = ingest(resolved_path, _qdrant, _embed, limit=args.limit)
    except Exception:  # noqa: BLE001
        import traceback  # noqa: PLC0415

        print("ERROR: ingestion failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    print(f"Done. speeches_processed={processed}  chunks_upserted={chunks}")
