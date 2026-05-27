"""Counterbalancer service for group assignment."""

import logging
import random
from typing import Literal

from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)

logger = logging.getLogger(__name__)

# Type for the 6 sub-groups (A=guided, B=baseline-free, C=baseline-capped;
# 1/2=topic counterbalance).
GroupType = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

GROUPS: list[GroupType] = ["A1", "A2", "B1", "B2", "C1", "C2"]


MAX_LEAD_OVER_MIN = 0


def compute_group_weights(counts: dict[GroupType, int]) -> list[int]:
    """
    Hard round-robin weighting.

    Any group whose count is more than ``MAX_LEAD_OVER_MIN`` ahead of the
    least-represented group gets weight ``0`` and is skipped on the next
    draw. Among the remaining groups the least-represented still gets the
    highest weight, so the loose randomness within the eligible window is
    preserved (avoids lockstep assignment under concurrent creates).

    Example with ``MAX_LEAD_OVER_MIN = 2`` and counts ``{A1: 2, A2: 0,
    B1: 4, B2: 2}``: min is ``0``, threshold is ``2``, so weights are
    ``[1, 3, 0, 1]`` — A2 is heavily favoured and B1 is excluded until
    others catch up.
    """
    min_count = min(counts.get(group, 0) for group in GROUPS)
    threshold = min_count + MAX_LEAD_OVER_MIN
    weights: list[int] = []
    for group in GROUPS:
        c = counts.get(group, 0)
        if c > threshold:
            weights.append(0)
        else:
            weights.append((threshold + 1) - c)
    return weights


class Counterbalancer:
    """
    Assigns participants to groups for between-subjects A/B design.

    Uses 6 sub-groups to counterbalance topic assignment across conditions:
    - Group A1: Guided + Topic1
    - Group A2: Guided + Topic2
    - Group B1: Baseline (free)   + Topic1
    - Group B2: Baseline (free)   + Topic2
    - Group C1: Baseline (capped) + Topic1
    - Group C2: Baseline (capped) + Topic2
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
