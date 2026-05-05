# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Resolves a context_id to its display name and party map, with TTL cache."""

import time

from src.firebase_service import aget_context_by_id, aget_parties_for_context
from src.guided_exploration.agents.party_context import (
    PartyInfo,
    parties_to_info_map,
)
from src.guided_exploration.services.study_context import (
    STUDY_PARTY_IDS,
    get_study_context_info,
    is_study_context,
)

# Context cache TTL: 1 hour. Context/party data changes infrequently; hourly
# refresh is more than sufficient.
CONTEXT_CACHE_TTL_SECONDS = 3600


class ContextResolver:
    """Loads (and caches) the context name + party info map for a context_id.

    Study contexts (``study-*``) bypass Firebase and use the static fake-party
    fixture from ``study_context``.
    """

    def __init__(self, ttl_seconds: int = CONTEXT_CACHE_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        # context_id -> (timestamp, context_name, parties_info_map)
        self._cache: dict[str, tuple[float, str, dict[str, PartyInfo]]] = {}

    async def get_context_info(
        self, context_id: str
    ) -> tuple[str, dict[str, PartyInfo]]:
        cached = self._cache.get(context_id)
        if cached is not None:
            ts, context_name, parties_info = cached
            if time.monotonic() - ts < self._ttl_seconds:
                return context_name, parties_info

        if is_study_context(context_id):
            context_name, parties_info = get_study_context_info(context_id)
            self._cache[context_id] = (time.monotonic(), context_name, parties_info)
            return context_name, parties_info

        context = await aget_context_by_id(context_id)
        context_name = context.name if context else context_id

        parties = await aget_parties_for_context(context_id)
        parties_info = parties_to_info_map(parties)

        self._cache[context_id] = (time.monotonic(), context_name, parties_info)
        return context_name, parties_info

    async def get_default_parties(self, context_id: str) -> list[str]:
        if is_study_context(context_id):
            return list(STUDY_PARTY_IDS)
        _, parties_info = await self.get_context_info(context_id)
        return list(parties_info.keys())
