# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Unit tests for difficulty-aware quiz sampling."""

from src.exploration_study.services.quiz_sampler import (
    HARD_PATTERNS,
    QUOTA_COMPARATIVE,
    QUOTA_EASY,
    QUOTA_HARD,
    _load_corpus,
    sample_quiz,
)


def _all_positions() -> list[str]:
    corpus = _load_corpus()
    return sorted({pid for e in corpus for pid in e.prerequisite_position_ids})


def _prereqs_by_question() -> dict[str, list[str]]:
    return {e.question: list(e.prerequisite_position_ids) for e in _load_corpus()}


def test_corpus_loads_and_validates():
    """The corpus parses and the difficulty/pattern invariants hold."""
    corpus = _load_corpus()

    easy_retention = [
        e for e in corpus if e.difficulty == "easy" and e.category == "retention"
    ]
    comparative = [e for e in corpus if e.category == "comparative"]
    hard = [e for e in corpus if e.difficulty == "hard"]

    assert len(easy_retention) == 42
    assert len(comparative) == 13
    assert len(hard) == 24

    for e in hard:
        assert e.category == "retention"
        assert e.hard_pattern in HARD_PATTERNS
    for e in corpus:
        if e.difficulty == "easy":
            assert e.hard_pattern is None

    # Each hard pattern is balanced across both topics (4 + 4).
    for pattern in HARD_PATTERNS:
        in_pattern = [e for e in hard if e.hard_pattern == pattern]
        topics = sorted(e.topic for e in in_pattern)
        assert topics.count("klimaschutz") == 4
        assert topics.count("soziale-gerechtigkeit") == 4


def test_full_eligibility_meets_quota():
    """With everything encountered, the quiz is exactly 5 / 3 / 2."""
    result = sample_quiz(_all_positions(), session_id="sess-1", n=10)

    assert len(result) == 10

    easy = [q for q in result if q.difficulty == "easy" and q.category == "retention"]
    comparative = [q for q in result if q.category == "comparative"]
    hard = [q for q in result if q.difficulty == "hard"]

    assert len(easy) == QUOTA_EASY
    assert len(comparative) == QUOTA_COMPARATIVE
    assert len(hard) == QUOTA_HARD
    # One of each hard pattern.
    assert sorted(q.hard_pattern for q in hard) == sorted(HARD_PATTERNS)


def test_no_duplicate_prerequisite_positions():
    """No two selected questions rest on the same underlying fact."""
    result = sample_quiz(_all_positions(), session_id="sess-xyz", n=10)

    prereqs = _prereqs_by_question()
    used: set[str] = set()
    for q in result:
        for pid in prereqs[q.question]:
            assert pid not in used, f"position {pid} reused"
            used.add(pid)


def test_deterministic_per_session():
    """Same session id yields the same questions (content) in the same order."""
    positions = _all_positions()
    first = sample_quiz(positions, session_id="sess-determinism", n=10)
    second = sample_quiz(positions, session_id="sess-determinism", n=10)

    assert [q.question for q in first] == [q.question for q in second]


def test_different_sessions_differ():
    """Different session seeds generally produce different selections/orders."""
    positions = _all_positions()
    a = [q.question for q in sample_quiz(positions, session_id="seed-a", n=10)]
    b = [q.question for q in sample_quiz(positions, session_id="seed-b", n=10)]

    assert a != b


def test_hard_backfills_within_bucket_when_pattern_missing():
    """When only one hard pattern is reachable, the hard bucket still fills to 3."""
    corpus = _load_corpus()
    detail_positions = sorted(
        {
            pid
            for e in corpus
            if e.difficulty == "hard" and e.hard_pattern == "detail"
            for pid in e.prerequisite_position_ids
        }
    )

    result = sample_quiz(detail_positions, session_id="sess-detail-only", n=10)

    hard = [q for q in result if q.difficulty == "hard"]
    assert len(hard) == QUOTA_HARD
    # No counter/transfer reachable, so all three hard picks are detail.
    assert all(q.hard_pattern == "detail" for q in hard)


def test_no_positions_yields_empty_quiz():
    """A participant who encountered nothing gets no questions."""
    assert sample_quiz([], session_id="sess-empty", n=10) == []
