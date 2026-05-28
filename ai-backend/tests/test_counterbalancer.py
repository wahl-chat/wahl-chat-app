# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Unit tests for the half-block counterbalancer."""

from collections import Counter

from src.exploration_study.services.counterbalancer import (
    BLOCK_SIZE,
    GROUPS,
    HALF_BLOCK_SIZE,
    SYSTEMS,
    assign_group_from_count,
)


def _block(study_id: str, block_index: int) -> list[str]:
    """Return the 6-group sequence assigned to a given block."""
    base = block_index * BLOCK_SIZE
    return [assign_group_from_count(study_id, base + i) for i in range(BLOCK_SIZE)]


def _system_of(group: str) -> str:
    return group[0]


def test_block_contains_each_group_exactly_once():
    """Every block of 6 fills each cell exactly once."""
    block = _block("study-A", 0)
    assert Counter(block) == Counter(GROUPS)


def test_each_half_block_contains_each_system_once():
    """Within a block, both halves of 3 are system-balanced (one A, B, C each)."""
    for block_index in range(10):
        block = _block("study-A", block_index)
        half1 = block[:HALF_BLOCK_SIZE]
        half2 = block[HALF_BLOCK_SIZE:]
        assert Counter(_system_of(g) for g in half1) == Counter(SYSTEMS), (
            f"block {block_index} half-1 not system-balanced: {half1}"
        )
        assert Counter(_system_of(g) for g in half2) == Counter(SYSTEMS), (
            f"block {block_index} half-2 not system-balanced: {half2}"
        )


def test_multiple_blocks_each_balanced():
    """Several consecutive blocks are each independently cell-balanced."""
    for block_index in range(5):
        block = _block("study-A", block_index)
        assert Counter(block) == Counter(GROUPS), (
            f"block {block_index} not balanced: {block}"
        )


def test_block_order_varies_across_blocks():
    """Different blocks produce different orderings (random per block)."""
    orderings = {tuple(_block("study-A", i)) for i in range(5)}
    assert len(orderings) >= 4


def test_assignment_deterministic_per_seed():
    """Same (study_id, total_count) always returns the same group."""
    for total in range(20):
        first = assign_group_from_count("study-A", total)
        second = assign_group_from_count("study-A", total)
        assert first == second


def test_different_studies_get_independent_permutations():
    """Two distinct study ids get independent block orderings."""
    block_a = _block("study-A", 0)
    block_b = _block("study-B", 0)
    assert Counter(block_a) == Counter(GROUPS)
    assert Counter(block_b) == Counter(GROUPS)
    assert block_a != block_b


def test_large_run_stays_balanced():
    """Over many blocks, the cumulative cell distribution stays exactly balanced."""
    n_blocks = 50
    counts: Counter[str] = Counter()
    for total in range(n_blocks * BLOCK_SIZE):
        counts[assign_group_from_count("study-A", total)] += 1
    expected = n_blocks
    for group in GROUPS:
        assert counts[group] == expected, f"group {group}: {counts[group]} != {expected}"


def test_system_balance_at_n_45():
    """N = 45 (7 full blocks + 1 half-block) yields exactly 15/15/15 systems."""
    counts: Counter[str] = Counter()
    for total in range(45):
        counts[_system_of(assign_group_from_count("study-A", total))] += 1
    assert counts == Counter({"A": 15, "B": 15, "C": 15}), counts


def test_system_balance_at_every_half_block_boundary():
    """At every multiple of 3, system counts differ by at most 0 (perfectly balanced)."""
    counts: Counter[str] = Counter()
    for total in range(20 * HALF_BLOCK_SIZE):
        counts[_system_of(assign_group_from_count("study-A", total))] += 1
        if (total + 1) % HALF_BLOCK_SIZE == 0:
            triples = (total + 1) // HALF_BLOCK_SIZE
            for system in SYSTEMS:
                assert counts[system] == triples, (
                    f"after {total + 1} assigns, system {system}: "
                    f"{counts[system]} != {triples}"
                )
