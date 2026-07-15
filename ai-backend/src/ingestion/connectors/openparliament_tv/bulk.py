# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Standalone --from-github bulk backfill for openparliament.tv speeches.

Enumerates the WP20+21 ``processed/*-session.json`` bulk files via ``OpTvClient``,
runs each session's speech items through ``build_chunk_records``, and embeds +
upserts into ``wahlchat_chunks_{ENV}`` in batches. The live connector
(``connector.py``) handles incremental runs via ``run.py`` and the YYYYMMDD cursor;
this script handles the one-shot historical backfill from GitHub.

Design notes:
  - This is the ONLY file within the ``openparliament_tv`` package permitted to call
    the runner ``_embed_texts`` / ``_upsert_chunks`` helpers directly. The connector
    never touches those — ``run.py`` owns that path.
  - Each record is stamped ``external_id=YYYYMMDD(dateStart)`` (same as
    ``normalize()``) so ``run.py``'s ``get_cursor("parliamentary_speech",
    source="op")`` picks up the backfill and the first live incremental run does not
    re-embed everything.
  - Idempotent: deterministic chunk UUIDs (``compute_chunk_id``) mean re-running
    upserts the same Qdrant point IDs (a no-op), and the ``content_hash`` guard
    re-writes only genuinely changed chunks.

Usage (local dev):
    cd ai-backend
    uv run python -m src.ingestion.connectors.openparliament_tv.bulk --help
    uv run python -m src.ingestion.connectors.openparliament_tv.bulk --from-github --limit 20
    QDRANT_URL=http://localhost:6333 ENV=dev \\
        uv run python -m src.ingestion.connectors.openparliament_tv.bulk --from-github

Requires: make stores-up first (Qdrant running at QDRANT_URL).
          OPENAI_API_KEY in ai-backend/.env (auto-loaded if present).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.bundestag_speeches.constants import MDB_STAMMDATEN_FILE
from src.ingestion.connectors.bundestag_speeches.mdb import load_mdb_lookup
from src.ingestion.connectors.openparliament_tv.client import OpTvClient
from src.ingestion.connectors.openparliament_tv.mappers.corpus import build_chunk_records
from src.ingestion.connectors.openparliament_tv.supersede import supersede_dip_duplicates
from src.ingestion.run import _embed_texts, _upsert_chunks
from src.ingestion.schemas import ChunkRecord
from src.ingestion.setup_collection import COLLECTION_NAME, EMBEDDING_MODEL

# Shared speech-dedup helper (C11) — one definition for both speech connectors.
from src.ingestion.speech_dedup import datum_to_external_id as _datum_to_external_id

logger = logging.getLogger(__name__)


class _OpSourceStub(BaseConnector):
    """Minimal connector stand-in for the supersede op source-gate (C4).

    ``supersede_dip_duplicates`` fires only for ``connector.source == "op"``;
    the backfill has no live connector instance, so this stub carries the gate.
    Only the class attributes are ever read — the pipeline methods are never
    called during a bulk backfill.
    """

    source_type = "parliamentary_speech"
    source = "op"

    def discover(self, since):  # noqa: ANN001, ANN201 — never called
        raise NotImplementedError("_OpSourceStub only carries the supersede source gate")

    def fetch(self, external_id):  # noqa: ANN001, ANN201 — never called
        raise NotImplementedError("_OpSourceStub only carries the supersede source gate")

    def normalize(self, raw):  # noqa: ANN001, ANN201 — never called
        raise NotImplementedError("_OpSourceStub only carries the supersede source gate")


_OP_GATE = _OpSourceStub()

_BATCH_SIZE = 100  # chunks per embed+upsert batch

# MdB-Stammdaten XML, resolved relative to ai-backend/ (bulk.py is 4 levels deep).
_MDB_PATH: Path = Path(__file__).resolve().parents[4] / MDB_STAMMDATEN_FILE


# =============================================================================
# MAIN INGEST LOOP
# =============================================================================


def ingest(
    client: OpTvClient,
    qdrant: QdrantClient,
    embed: OpenAIEmbeddings,
    mdb_lookup: dict,
    limit: Optional[int] = None,
) -> tuple[int, int]:
    """Enumerate WP20+21 session files and upsert their aligned speeches in batches.

    Each raw session ``data[]`` item is passed through ``build_chunk_records`` (which
    applies the D-03 alignment gate); usable speeches are stamped with
    ``external_id=YYYYMMDD(dateStart)`` so ``get_cursor`` picks up the backfill.

    Args:
        client:     Initialised OpTvClient.
        qdrant:     Initialised QdrantClient.
        embed:      Initialised OpenAIEmbeddings instance.
        mdb_lookup: MdB-Stammdaten lookup for the empty-faction / CSU fallback.
        limit:      Maximum number of usable speeches to process (None = all).

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
        # C4: supersede each flushed batch's DIP twins immediately. Without this
        # the entire historical overlap stays duplicated forever: later live runs
        # see the backfilled sessions as present-skips, so the post_upsert hook
        # never fires for them and the PDF graft never happens.
        supersede_dip_duplicates(qdrant, COLLECTION_NAME, b, connector=_OP_GATE)
        return len(b)

    session_files = client.list_session_files()
    logger.info("op backfill: %d WP20+21 session files to scan.", len(session_files))

    for name in session_files:
        if limit is not None and speeches_processed >= limit:
            break

        try:
            session = client.fetch_session_json(name)
        except Exception as exc:  # noqa: BLE001 — a bad session file must not abort the backfill
            logger.warning("op backfill: fetch failed for %s (%s) — skipping.", name, exc)
            continue

        for item in session.get("data") or []:
            if not isinstance(item, dict):
                continue
            if limit is not None and speeches_processed >= limit:
                break

            records = build_chunk_records(item, mdb_lookup)
            if not records:
                # Unaligned / ASR-only / empty-text item — D-03 skip (not counted).
                continue

            ext = _datum_to_external_id(item.get("dateStart"))
            if ext is not None:
                records = [c.model_copy(update={"external_id": ext}) for c in records]

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
    # Load ai-backend/.env if present. bulk.py is 4 levels deep → parents[4] = ai-backend/.
    from dotenv import load_dotenv  # noqa: PLC0415

    _env_path = Path(__file__).resolve().parents[4] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description=(
            "Backfill openparliament.tv WP20+21 speeches from the keyless GitHub bulk "
            "repository into the Qdrant wahlchat_chunks_{ENV} collection. No API key "
            "required — reads processed/*-session.json, not the live op API."
        ),
    )
    parser.add_argument(
        "--from-github",
        dest="from_github",
        action="store_true",
        help="Enumerate + backfill from the OpenParliamentTV-Data-DE GitHub bulk repo.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N usable speeches (for smoke testing).",
    )
    args = parser.parse_args()

    if not args.from_github:
        print(
            "ERROR: nothing to do — pass --from-github to run the GitHub bulk backfill.",
            file=sys.stderr,
        )
        sys.exit(2)

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    _qdrant = QdrantClient(url=qdrant_url)
    _embed = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    _client = OpTvClient()
    _mdb_lookup = load_mdb_lookup(_MDB_PATH)

    print(f"Backfilling openparliament.tv speeches from GitHub (limit={args.limit}) ...")
    try:
        processed, chunks = ingest(_client, _qdrant, _embed, _mdb_lookup, limit=args.limit)
    except Exception:  # noqa: BLE001
        import traceback  # noqa: PLC0415

        print("ERROR: backfill failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    print(f"Done. speeches_processed={processed}  chunks_upserted={chunks}")
