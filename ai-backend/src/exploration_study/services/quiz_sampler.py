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
from uuid import uuid4

from pydantic import BaseModel, Field

from src.exploration_study.models.quiz import QuizQuestion

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "study-fake-parties"
CORPUS_PATH = DATA_DIR / "quiz_questions.json"
POSITIONS_DIR = DATA_DIR / "positions"


class _CorpusEntry(BaseModel):
    """A single corpus entry. Options are 3-4 content choices; the
    don't-know affordance is rendered by the frontend as a separate UI
    control and is not part of the data."""

    id: str
    question: str
    options: list[str] = Field(min_length=3, max_length=3)
    correct_index: int = Field(ge=0, le=2)
    topic: str
    prerequisite_position_ids: list[str] = Field(min_length=1, max_length=2)
    is_overlap_question: bool = False


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
    )


def sample_quiz(
    positions_encountered: list[str],
    session_id: str,
    n: int = 10,
) -> list[QuizQuestion]:
    """Sample up to ``n`` questions whose prerequisites are all encountered.

    Shuffle is seeded by ``session_id`` so the same participant always
    sees the same questions in the same order if the quiz is regenerated.
    Returns fewer than ``n`` questions when fewer are eligible (or zero
    if the participant encountered no positions whose questions are
    answerable).
    """
    corpus = _load_corpus()
    encountered = set(positions_encountered)

    eligible = [
        e
        for e in corpus
        if all(pid in encountered for pid in e.prerequisite_position_ids)
    ]

    rng = random.Random(session_id)
    rng.shuffle(eligible)
    selected = eligible[:n]

    logger.info(
        f"Sampled {len(selected)}/{len(eligible)} eligible quiz questions "
        f"for session {session_id} (corpus={len(corpus)}, "
        f"positions_encountered={len(encountered)})"
    )
    return [_to_quiz_question(e) for e in selected]
