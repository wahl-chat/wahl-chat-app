# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Store for queries waiting on a user choice (explore-vs-summary, directions)."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Pending-query TTL: 30 minutes. Abandoned sessions never call handle_choice,
# so entries must be evicted proactively to prevent unbounded growth.
PENDING_QUERY_TTL_SECONDS = 1800


class PendingQuery:
    """A query awaiting a user choice (summary vs. explore, or topic direction)."""

    def __init__(
        self,
        query_id: str,
        session_id: str,
        original_query: str,
        detected_parties: list[str],
        rag_query: str,
        selected_direction: str | None = None,
    ) -> None:
        self.query_id = query_id
        self.session_id = session_id
        self.original_query = original_query
        self.detected_parties = detected_parties
        self.rag_query = rag_query
        self.selected_direction = selected_direction
        self.created_at = datetime.now(timezone.utc)


class PendingQueryStore:
    """In-memory pending-query registry with TTL eviction.

    Entries are normally removed when the user makes a choice. This store
    handles the abandoned-session case by evicting anything older than
    ``ttl_seconds`` whenever a new entry is registered.
    """

    def __init__(self, ttl_seconds: int = PENDING_QUERY_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, PendingQuery] = {}

    def register(self, pending: PendingQuery) -> None:
        self.evict_stale()
        self._entries[pending.query_id] = pending

    def get(self, query_id: str) -> PendingQuery | None:
        return self._entries.get(query_id)

    def pop(self, query_id: str) -> PendingQuery | None:
        return self._entries.pop(query_id, None)

    def evict_stale(self) -> None:
        now = datetime.now(timezone.utc)
        stale = [
            qid
            for qid, pq in self._entries.items()
            if (now - pq.created_at).total_seconds() > self._ttl_seconds
        ]
        for qid in stale:
            del self._entries[qid]
        if stale:
            logger.debug(f"Evicted {len(stale)} stale pending queries")
