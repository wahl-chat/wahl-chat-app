"""Sample quiz questions from a hand-authored corpus.

Replaces the previous LLM-based quiz generator. The corpus lives at
``ai-backend/data/study-fake-parties/quiz_questions.json`` and stores
questions tagged with ``prerequisite_position_ids`` — the master position
ids whose content the question is based on. A question is only sampled
for a participant if every prerequisite was encountered during their
guided exploration session.
"""

import json
import logging
import random
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from src.exploration_study.models.quiz import QuizQuestion

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "study-fake-parties"
CORPUS_PATH = DATA_DIR / "quiz_questions.json"
POSITIONS_DIR = DATA_DIR / "positions"

# Quiz composition: 5 easy single-party + 3 hard single-party (one per
# hard pattern) + 2 comparative (two-party) questions = 10.
HARD_PATTERNS: tuple[str, ...] = ("detail", "counter_stereotype", "transfer")
QUOTA_EASY = 5
QUOTA_HARD = 3
QUOTA_COMPARATIVE = 2


class _CorpusEntry(BaseModel):
    """A single corpus entry. Options are 3 content choices; the
    don't-know affordance is rendered by the frontend as a separate UI
    control and is not part of the data."""

    id: str
    question: str
    options: list[str] = Field(min_length=3, max_length=3)
    correct_index: int = Field(ge=0, le=2)
    topic: str
    prerequisite_position_ids: list[str] = Field(min_length=1, max_length=2)
    is_overlap_question: bool = False
    category: Literal["retention", "comparative"] = "retention"
    difficulty: Literal["easy", "hard"] = "easy"
    hard_pattern: Literal["detail", "counter_stereotype", "transfer"] | None = None

    @model_validator(mode="after")
    def _check_difficulty(self) -> "_CorpusEntry":
        if self.difficulty == "hard":
            if self.hard_pattern is None:
                raise ValueError(f"hard question {self.id} must set hard_pattern")
            if self.category != "retention":
                raise ValueError(
                    f"hard question {self.id} must be category 'retention'"
                )
        elif self.hard_pattern is not None:
            raise ValueError(
                f"easy question {self.id} must not set hard_pattern"
            )
        return self


_corpus_cache: list[_CorpusEntry] | None = None


def _load_position_ids() -> set[str]:
    ids: set[str] = set()
    for path in sorted(POSITIONS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            for entry in json.load(f):
                ids.add(entry["id"])
    return ids


def _load_corpus() -> list[_CorpusEntry]:
    global _corpus_cache
    if _corpus_cache is not None:
        return _corpus_cache

    with open(CORPUS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    entries = [_CorpusEntry(**item) for item in raw]

    valid_position_ids = _load_position_ids()
    seen_ids: set[str] = set()
    for entry in entries:
        if entry.id in seen_ids:
            raise ValueError(f"Duplicate quiz question id: {entry.id}")
        seen_ids.add(entry.id)
        for pid in entry.prerequisite_position_ids:
            if pid not in valid_position_ids:
                raise ValueError(
                    f"Quiz question {entry.id} references unknown position {pid}"
                )

    _corpus_cache = entries
    return entries


def _to_quiz_question(entry: _CorpusEntry) -> QuizQuestion:
    return QuizQuestion(
        id=str(uuid4()),
        question=entry.question,
        options=list(entry.options),
        correct_index=entry.correct_index,
        topic=entry.topic,
        is_overlap_question=entry.is_overlap_question,
        category=entry.category,
        difficulty=entry.difficulty,
        hard_pattern=entry.hard_pattern,
    )


def sample_quiz(
    positions_encountered: list[str],
    session_id: str,
    n: int = 10,
) -> list[QuizQuestion]:
    """Sample a quiz of up to ``n`` questions, split by bucket.

    The target composition is 5 easy single-party + 3 hard single-party
    (one per hard pattern) + 2 comparative questions. A question is only
    eligible if every prerequisite position was encountered during the
    session. No two selected questions share a prerequisite position, so a
    quiz never asks twice about the same underlying fact.

    Shortfalls degrade gracefully: an empty hard pattern is backfilled from
    the other hard patterns, and any bucket that cannot meet its quota is
    backfilled from leftover eligible questions (easy, then comparative,
    then hard) so the quiz still reaches ``n`` where possible.

    Shuffles are seeded by ``session_id`` so the same participant always
    sees the same questions in the same order if the quiz is regenerated.
    """
    corpus = _load_corpus()
    encountered = set(positions_encountered)

    eligible = [
        e
        for e in corpus
        if all(pid in encountered for pid in e.prerequisite_position_ids)
    ]

    rng = random.Random(session_id)
    rng.shuffle(eligible)  # bucket views below preserve this deterministic order

    easy_pool = [
        e for e in eligible if e.difficulty == "easy" and e.category == "retention"
    ]
    comparative_pool = [e for e in eligible if e.category == "comparative"]
    hard_by_pattern = {
        p: [e for e in eligible if e.difficulty == "hard" and e.hard_pattern == p]
        for p in HARD_PATTERNS
    }

    selected: list[_CorpusEntry] = []
    selected_ids: set[str] = set()
    used_positions: set[str] = set()

    def take(candidates: list[_CorpusEntry], k: int) -> int:
        """Append up to ``k`` candidates that don't reuse a prerequisite."""
        taken = 0
        for e in candidates:
            if taken >= k:
                break
            if e.id in selected_ids:
                continue
            if any(pid in used_positions for pid in e.prerequisite_position_ids):
                continue
            selected.append(e)
            selected_ids.add(e.id)
            used_positions.update(e.prerequisite_position_ids)
            taken += 1
        return taken

    # 3 hard: one of each pattern, then backfill from any pattern.
    hard_taken = sum(take(hard_by_pattern[p], 1) for p in HARD_PATTERNS)
    all_hard = [e for p in HARD_PATTERNS for e in hard_by_pattern[p]]
    if hard_taken < QUOTA_HARD:
        hard_taken += take(all_hard, QUOTA_HARD - hard_taken)

    easy_taken = take(easy_pool, QUOTA_EASY)
    comparative_taken = take(comparative_pool, QUOTA_COMPARATIVE)

    # Backfill to ``n`` if any bucket fell short: easy, then comparative, then hard.
    if len(selected) < n:
        take(easy_pool + comparative_pool + all_hard, n - len(selected))

    rng.shuffle(selected)  # mix difficulties in the presented order
    selected = selected[:n]

    logger.info(
        f"Sampled {len(selected)} quiz questions for session {session_id}: "
        f"easy={easy_taken}/{QUOTA_EASY}, hard={hard_taken}/{QUOTA_HARD}, "
        f"comparative={comparative_taken}/{QUOTA_COMPARATIVE} "
        f"(eligible={len(eligible)}, corpus={len(corpus)}, "
        f"positions_encountered={len(encountered)})"
    )
    return [_to_quiz_question(e) for e in selected]
