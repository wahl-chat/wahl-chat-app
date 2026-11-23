# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Feed items that match a question, shown as a carousel under the answer.

Searches the feed's semantic index (written by ingestion's ``feed/index.py``)
with the corpus's query embedding. Raw scores shift with a question's wording
("Was passiert gerade im Bundestag?" scores every item high, "Mercosur" every
item low), so an item counts by its lead over the background: the score at a
fixed rank.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional, Sequence

from qdrant_client import models

from src.retrieve import _get_qdrant, embed_query
from wahlchat_common.corpus import FEED_COLLECTION_NAME, acheck_fingerprint

logger = logging.getLogger(__name__)

ENV = "GENERIC_CHAT_RELATED_ITEMS"
# Parliaments with a feed index.
FEED_PARLIAMENTS: frozenset[str] = frozenset({"bundestag"})
# A follow-up this short ("Und die SPD?") says too little to search on.
MIN_FOLLOW_UP_WORDS = 5
# A missing or too small index is not searched again for this long.
UNAVAILABLE_S = 300.0
MAX_ITEMS = 5
# Measured on the dev feed: unrelated questions lead by at most 0.064,
# questions with a matching item by 0.06 to 0.23.
BASELINE_RANK = 50
MIN_LEAD = 0.065
# A tail far behind a clear match ("Mercosur": 0.17, then 0.04) is dropped.
LEAD_RATIO = 0.6
# Leads in the same band of this width count as equal; the newer item
# comes first.
TIE = 0.01

_checked: set[int] = set()
_unavailable_until: dict[str, float] = {}


def enabled() -> bool:
    return os.getenv(ENV, "on") != "off"


def wanted(parliament: Optional[str], question: str, has_history: bool) -> bool:
    """Whether a turn without an anchor searches at all."""
    if not enabled() or parliament not in FEED_PARLIAMENTS:
        return False
    if has_history and len(question.split()) < MIN_FOLLOW_UP_WORDS:
        return False
    return _unavailable_until.get(parliament, 0.0) <= time.monotonic()


def _mark_unavailable(parliament: str) -> None:
    _unavailable_until[parliament] = time.monotonic() + UNAVAILABLE_S


def select(
    hits: Sequence[tuple[str, float, str]], baseline_rank: int = BASELINE_RANK
) -> list[str]:
    """Ids of the items that clearly lead the background, from (id, score,
    ISO date) in score order; none when the collection is too small to have
    a background."""
    if len(hits) < baseline_rank:
        return []
    background = hits[baseline_rank - 1][1]
    leads = [(item_id, score - background, day) for item_id, score, day in hits]
    best = leads[0][1]
    cutoff = max(MIN_LEAD, best * LEAD_RATIO)
    picked = [lead for lead in leads if lead[1] >= cutoff]
    picked.sort(key=lambda lead: (int(lead[1] / TIE), lead[2]), reverse=True)
    return [item_id for item_id, _lead, _day in picked[:MAX_ITEMS]]


async def find(query: str, parliament: str, client: Optional[Any] = None) -> list[str]:
    """Published items of ``parliament`` that match ``query``, best first."""
    client = client if client is not None else _get_qdrant()
    vector = await embed_query(query)
    try:
        if id(client) not in _checked:
            await acheck_fingerprint(client, FEED_COLLECTION_NAME)
        response = await client.query_points(
            collection_name=FEED_COLLECTION_NAME,
            query=vector,
            using="dense",
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="status", match=models.MatchValue(value="published")
                    ),
                    models.FieldCondition(
                        key="parliament", match=models.MatchValue(value=parliament)
                    ),
                ]
            ),
            limit=BASELINE_RANK,
            with_payload=["item_id", "date"],
        )
    except Exception:
        # A missing collection or a fingerprint mismatch; retried after
        # UNAVAILABLE_S.
        _mark_unavailable(parliament)
        raise
    _checked.add(id(client))
    hits = [
        (str(payload["item_id"]), float(point.score), str(payload.get("date") or ""))
        for point in response.points
        if (payload := point.payload or {}).get("item_id")
    ]
    if len(hits) < BASELINE_RANK:
        logger.info(
            "related feed items: only %d %s items indexed", len(hits), parliament
        )
        _mark_unavailable(parliament)
    return select(hits)


async def safe_find(query: str, parliament: str) -> list[str]:
    """``find`` that never raises: the carousel is optional."""
    started = time.monotonic()
    try:
        items = await find(query, parliament)
    except Exception as exc:  # noqa: BLE001 (no carousel, the answer stands)
        logger.warning("related feed items failed: %r", exc)
        return []
    logger.info(
        "related feed items: %d in %.1fs", len(items), time.monotonic() - started
    )
    return items
