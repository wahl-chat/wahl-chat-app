"""Counterbalancer service for group assignment.

Each block of ``BLOCK_SIZE`` (= 6) participants fills every cell A1/A2/B1/B2/
C1/C2 exactly once. The block is built from two half-blocks of 3, each a
random permutation of the systems ``A/B/C``; the two topic slots for each
system are split across the halves (one half gets topic 1, the other topic 2,
in random order). The half-block structure means **every 3 consecutive
assignments** form a complete A/B/C triple, so the primary system axis stays
within ±0 of perfect balance whenever ``N % 3 == 0`` (e.g. N = 45 → 15/15/15)
instead of only when ``N % 6 == 0``.

The assignment is stateless — derived from ``total_count`` and ``study_id``
alone — so the count read and the session write must share a Firestore
transaction for the assignment to be safe under concurrency. That transaction
lives in :class:`SessionRepository`; see ``create_session_with_assigned_group``
and ``claim_or_create_self_serve_session``. The ``Counterbalancer`` class here
only exposes a read-only ``get_group_counts`` helper for admin views.
"""

import logging
import random
from typing import Literal, cast

from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)

logger = logging.getLogger(__name__)

# Type for the 6 sub-groups (A=guided, B=baseline-free, C=baseline-capped;
# 1/2=topic counterbalance).
GroupType = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

GROUPS: list[GroupType] = ["A1", "A2", "B1", "B2", "C1", "C2"]
BLOCK_SIZE = 6
HALF_BLOCK_SIZE = 3
SYSTEMS: list[str] = ["A", "B", "C"]


def _build_block(study_id: str, block_index: int) -> list[GroupType]:
    """Return the 6-cell sequence for a single block.

    The two halves are independent random permutations of the systems, with
    topics paired across halves so each cell appears exactly once.
    """
    rng = random.Random(f"{study_id}:{block_index}")

    half1_systems = SYSTEMS.copy()
    rng.shuffle(half1_systems)
    half2_systems = SYSTEMS.copy()
    rng.shuffle(half2_systems)

    # For each system, decide whether the first appearance gets topic 1 or 2.
    # The other appearance gets the complementary topic, so every cell
    # (A1/A2/B1/B2/C1/C2) lands exactly once in the block.
    first_topic = {s: rng.choice([1, 2]) for s in SYSTEMS}

    block: list[GroupType] = []
    for system in half1_systems:
        block.append(cast(GroupType, f"{system}{first_topic[system]}"))
    for system in half2_systems:
        other = 1 if first_topic[system] == 2 else 2
        block.append(cast(GroupType, f"{system}{other}"))
    return block


def assign_group_from_count(study_id: str, total_count: int) -> GroupType:
    """Pick the group for the ``(total_count + 1)``-th session of ``study_id``."""
    block_index = total_count // BLOCK_SIZE
    position_in_block = total_count % BLOCK_SIZE
    return _build_block(study_id, block_index)[position_in_block]


class Counterbalancer:
    """Read-only helper for admin views of the current group distribution."""

    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repo = session_repository

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
