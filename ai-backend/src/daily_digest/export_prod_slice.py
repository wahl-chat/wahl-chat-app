# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Copy the recent votes + speeches the digest needs from prod Qdrant to local.

Local development runs against local stores only; this pulls just the slice a
digest reads instead of restoring a full prod snapshot. The prod client is
used for ``scroll`` only — this tool never writes to prod. The prod endpoint
comes from ``PROD_QDRANT_URL`` / ``PROD_QDRANT_API_KEY``, deliberately not
``QDRANT_URL``, so a leftover prod URL in the shell can never become the write
target.

Usage:
    export PROD_QDRANT_URL=https://<host>:6333 PROD_QDRANT_API_KEY=...
    uv run python -m src.daily_digest.export_prod_slice --days 45
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient, models

from src.daily_digest.parliaments import PARLIAMENTS
from src.daily_digest.reader import SPEECH_SOURCE_TYPE, VOTE_SOURCE_TYPE
from src.ingestion.setup_collection import COLLECTION_NAME, check_fingerprint, setup

logger = logging.getLogger(__name__)

_PAGE = 256


def slice_filter(since: date) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="source_type",
                match=models.MatchAny(any=[VOTE_SOURCE_TYPE, SPEECH_SOURCE_TYPE]),
            ),
            models.FieldCondition(
                key="region",
                match=models.MatchAny(
                    any=sorted({p.region for p in PARLIAMENTS.values()})
                ),
            ),
            models.FieldCondition(
                key="publish_date",
                range=models.DatetimeRange(
                    gte=datetime.combine(since, time.min, tzinfo=timezone.utc)
                ),
            ),
        ]
    )


def copy_slice(
    source: QdrantClient,
    source_collection: str,
    target: QdrantClient,
    target_collection: str,
    since: date,
) -> int:
    copied = 0
    offset = None
    while True:
        points, offset = source.scroll(
            collection_name=source_collection,
            scroll_filter=slice_filter(since),
            limit=_PAGE,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if points:
            target.upsert(
                collection_name=target_collection,
                points=[
                    models.PointStruct(id=p.id, vector=p.vector, payload=p.payload)
                    for p in points
                ],
                wait=True,
            )
            copied += len(points)
            logger.info("copied %d points", copied)
        if offset is None:
            return copied


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Copy recent votes and speeches from prod Qdrant into local Qdrant."
    )
    parser.add_argument(
        "--days", type=int, default=45, help="How far back to copy (default: 45)"
    )
    parser.add_argument(
        "--source-collection",
        default="wahlchat_chunks_prod",
        help="Collection to read on the prod cluster (default: wahlchat_chunks_prod)",
    )
    args = parser.parse_args(argv)

    prod_url = os.getenv("PROD_QDRANT_URL")
    if not prod_url:
        print(
            "PROD_QDRANT_URL is required (plus PROD_QDRANT_API_KEY).", file=sys.stderr
        )
        return 2
    local_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    if local_url.rstrip("/") == prod_url.rstrip("/"):
        print(
            "QDRANT_URL points at the prod cluster; refusing to copy onto itself.",
            file=sys.stderr,
        )
        return 2

    source = QdrantClient(
        url=prod_url, api_key=os.getenv("PROD_QDRANT_API_KEY") or None
    )
    target = QdrantClient(url=local_url, api_key=os.getenv("QDRANT_API_KEY") or None)

    # Both sides must be in the configured vector space, or the local store
    # would silently mix embedding models.
    check_fingerprint(source, args.source_collection)
    setup(target)
    check_fingerprint(target, COLLECTION_NAME)

    since = date.today() - timedelta(days=args.days)
    copied = copy_slice(source, args.source_collection, target, COLLECTION_NAME, since)
    print(f"copied {copied} points since {since} into {COLLECTION_NAME} at {local_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
