# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""TTL'd cache for topic-scout outputs keyed on (query, context_id)."""

import logging
import time

from src.guided_exploration.agents.topic_scout import TopicScoutOutput

logger = logging.getLogger(__name__)

# Directions cache TTL: 6 hours. Scout outputs are stable for a topic; a
# longer TTL reduces LLM calls without meaningful staleness risk.
DIRECTIONS_CACHE_TTL_SECONDS = 21600


class DirectionsCache:
    """Cache scout outputs flagged as reusable by the LLM.

    Misses (and expired hits) return None. ``put`` is the caller's
    responsibility — only call it when ``output.cacheable`` is true.
    """

    def __init__(self, ttl_seconds: int = DIRECTIONS_CACHE_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[tuple[str, str], tuple[float, TopicScoutOutput]] = {}

    def get(self, query: str, context_id: str) -> TopicScoutOutput | None:
        cached = self._entries.get((query, context_id))
        if cached is None:
            return None
        ts, value = cached
        if time.monotonic() - ts >= self._ttl_seconds:
            return None
        return value

    def put(self, query: str, context_id: str, value: TopicScoutOutput) -> None:
        self._entries[(query, context_id)] = (time.monotonic(), value)
        logger.info(f"Cached topic directions for: '{query}'")
