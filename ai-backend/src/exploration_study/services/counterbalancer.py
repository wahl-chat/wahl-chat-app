"""Counterbalancer service for group assignment."""

import logging
from typing import Literal

from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)

logger = logging.getLogger(__name__)

# Type for the 4 sub-groups (A=guided, B=baseline; 1/2=topic counterbalance)
GroupType = Literal["A1", "A2", "B1", "B2"]


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

    async def assign_group(self, study_id: str) -> GroupType:
        """
        Assign a group for a new session.

        Assigns to the group with fewest sessions to maintain balance.
        """
        counts = await self._session_repo.count_sessions_by_group(study_id)

        # Find the group with minimum count
        min_count = min(counts.values())
        groups: list[GroupType] = ["A1", "A2", "B1", "B2"]
        selected_group: GroupType = "A1"  # Default
        for group in groups:
            if counts.get(group, 0) == min_count:
                selected_group = group
                break

        logger.info(
            f"Assigned group {selected_group} for study {study_id} "
            f"(current counts: {counts})"
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
