"""Counterbalancer service for group assignment."""

import logging
import random
from typing import Literal

from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)

logger = logging.getLogger(__name__)

# Type for the 4 sub-groups (A=guided, B=baseline; 1/2=topic counterbalance)
GroupType = Literal["A1", "A2", "B1", "B2"]

GROUPS: list[GroupType] = ["A1", "A2", "B1", "B2"]


def compute_group_weights(counts: dict[GroupType, int]) -> list[int]:
    """
    Weight each group as ``(max_count + 1) - count`` so the least-represented
    group gets the highest weight while every group keeps a non-zero chance.
    """
    max_count = max(counts.values()) if counts else 0
    return [(max_count + 1) - counts.get(group, 0) for group in GROUPS]


class Counterbalancer:
    """
    Assigns participants to groups for between-subjects A/B design.

    Uses 4 sub-groups to counterbalance topic assignment across conditions:
    - Group A1: Guided + Topic1
    - Group A2: Guided + Topic2
    - Group B1: Baseline + Topic1
    - Group B2: Baseline + Topic2
    """

    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repo = session_repository

    async def assign_group(
        self,
        study_id: str,
        rng: random.Random | None = None,
    ) -> GroupType:
        """
        Assign a group for a new session via weighted random sampling.

        The least-represented group gets the highest weight, so on average
        the distribution stays balanced, but a small amount of randomness
        is preserved to avoid lockstep assignment under concurrent creates.
        """
        counts = await self._session_repo.count_sessions_by_group(study_id)
        weights = compute_group_weights(counts)
        picker = rng if rng is not None else random
        selected_group: GroupType = picker.choices(GROUPS, weights=weights, k=1)[0]

        logger.info(
            f"Assigned group {selected_group} for study {study_id} "
            f"(counts={counts}, weights={dict(zip(GROUPS, weights))})"
        )
        return selected_group

    async def get_group_counts(
        self,
        study_id: str,
    ) -> dict[GroupType, int]:
        """Get current group counts for a study."""
        return await self._session_repo.count_sessions_by_group(study_id)


# Singleton instance
_counterbalancer: Counterbalancer | None = None


def get_counterbalancer() -> Counterbalancer:
    """Get or create the global counterbalancer."""
    global _counterbalancer
    if _counterbalancer is None:
        _counterbalancer = Counterbalancer(get_session_repository())
    return _counterbalancer
