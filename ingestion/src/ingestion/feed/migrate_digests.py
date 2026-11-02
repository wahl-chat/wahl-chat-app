# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Move stored ``daily_digests`` docs to ``feed_editions`` + ``feed_items``.

No German text is generated again: the stored digests are split as they are,
each item keeps its old key in ``legacy_keys``. Translation and indexing are
the same steps the builder runs, and both are optional. ``daily_digests`` is
left untouched, so the web that still reads it keeps working until it is
switched over.

Usage (local):
    FIRESTORE_EMULATOR_HOST=localhost:8081 uv run python -m ingestion.feed.migrate_digests
    uv run python -m ingestion.feed.migrate_digests \
        --from-json ../firebase/firestore_data/emulator/daily_digests.json \
        --dry-run --out /tmp/feed.json
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time. override=False keeps exported
# variables (make, CI, the job spec) in force; Cloud Run has no .env.
if __name__ == "__main__":
    from pathlib import Path as _Path

    from dotenv import load_dotenv

    _env_path = _Path(__file__).resolve().parents[3] / ".env"
    # Use ai-backend/.env when ingestion/.env does not exist.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from ingestion.feed.bulk import _embeddings, _firestore_client, publish
from ingestion.feed.builder import DigestBuilder
from ingestion.feed.models import DailyDigest
from ingestion.firestore_guard import guard_firestore_target

logger = logging.getLogger(__name__)

LEGACY_COLLECTION = "daily_digests"


def read_legacy_digests(db: Any) -> list[DailyDigest]:
    return [
        DailyDigest.model_validate(s.to_dict())
        for s in db.collection(LEGACY_COLLECTION).stream()
    ]


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Split stored daily digests into feed editions and items."
    )
    parser.add_argument(
        "--from-json", type=Path, help="Read digests from this file, not Firestore"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Write neither Firestore nor Qdrant"
    )
    parser.add_argument("--out", type=Path, help="Also write the result as JSON")
    parser.add_argument(
        "--translate", action="store_true", help="Also translate (LLM calls)"
    )
    parser.add_argument(
        "--index", action="store_true", help="Also write the semantic index"
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit writes to non-emulator Firestore when ENV != prod",
    )
    args = parser.parse_args(argv)

    db = None
    if not args.dry_run or not args.from_json:
        guard_firestore_target("the feed migration", allow_remote=args.allow_remote)
        db = _firestore_client()

    if args.from_json:
        digests = [
            DailyDigest.model_validate(d)
            for d in json.loads(args.from_json.read_text(encoding="utf-8"))
        ]
    else:
        digests = read_legacy_digests(db)
    write_db = None if args.dry_run else db

    qdrant = None
    if args.index and not args.dry_run:
        from qdrant_client import QdrantClient  # noqa: PLC0415

        qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
        )

    builder = DigestBuilder()
    try:
        published = publish(
            digests,
            db=write_db,
            builder=builder,
            qdrant=qdrant,
            embed=_embeddings() if qdrant is not None else None,
            translate=args.translate,
        )
    finally:
        builder.close()

    t = published.translation
    print(
        f"digests={len(digests)} editions={len(published.editions)} "
        f"items={len(published.items)} translated={t.translated} "
        f"translation_failed={t.failed} indexed={published.index.upserted}"
    )
    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "editions": [e.model_dump(mode="json") for e in published.editions],
                    "items": [i.model_dump(mode="json") for i in published.items],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    # Same native-extension teardown crash as the builder after Gemini calls.
    os._exit(exit_code)
