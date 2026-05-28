"""Quiz models for knowledge retention measurement."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QuizStatus(str, Enum):
    """Status of quiz generation."""

    PENDING = "pending"
    READY = "ready"


DONT_KNOW_INDEX = -1

# Quiz corpus version. Bump when the answer-key positions change so that
# downstream analysis can compare like-for-like; older quizzes saved with
# ``version=None`` implicitly belong to the original (v1) corpus.
#
# v3 adds difficulty-aware sampling: each quiz is composed as 5 easy +
# 3 hard (one per hard pattern) + 2 comparative questions.
# v4 adjusts some of the hard questions to be better distributed
#
QUIZ_CORPUS_VERSION = "v4"


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question with 3 substantive options.

    The "Weiß ich nicht" abstain is rendered by the frontend as a
    separate UI control and is not part of ``options``.
    """

    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The question text")
    options: list[str] = Field(
        ...,
        description="Three substantive answer options",
        min_length=3,
        max_length=3,
    )
    correct_index: int = Field(
        ...,
        description="Index of the correct answer (0-2)",
        ge=0,
        le=2,
    )
    is_overlap_question: bool = Field(
        default=False,
        description="True if the question targets a known cross-party overlap.",
    )
    topic: str = Field(..., description="The topic this question covers")
    # The next three carry the sampling metadata through to persistence so
    # downstream analysis can break results down by bucket. Defaults keep
    # legacy quizzes (saved before v3) loadable as easy retention questions.
    category: str = Field(
        default="retention",
        description="'retention' (single-party) or 'comparative' (two-party).",
    )
    difficulty: str = Field(
        default="easy",
        description="'easy' or 'hard'.",
    )
    hard_pattern: str | None = Field(
        default=None,
        description="For hard questions: 'detail', 'counter_stereotype' or 'transfer'.",
    )


class QuizAnswer(BaseModel):
    """A participant's answer to a quiz question.

    ``selected_index`` is 0-2 for substantive options; ``-1`` indicates
    the participant chose the UI abstain ("Weiß ich nicht"). Scoring is
    binary: correct (1.0) or wrong (0.0).
    """

    question_id: str = Field(..., description="ID of the question being answered")
    selected_index: int = Field(
        ...,
        description="Selected option index (0-2); -1 = 'Weiß ich nicht' abstain",
        ge=-1,
        le=2,
    )
    is_correct: bool = Field(..., description="True if fully correct.")
    response_time_ms: int | None = Field(
        default=None,
        description="Time taken to answer in milliseconds",
    )


class Quiz(BaseModel):
    """A complete quiz generated for a task."""

    model_config = {"extra": "ignore", "use_enum_values": True}

    id: str = Field(..., description="Unique quiz identifier")
    session_id: str = Field(..., description="The session this quiz belongs to")
    status: QuizStatus = Field(
        default=QuizStatus.PENDING,
        description="Current status of quiz generation",
    )
    questions: list[QuizQuestion] = Field(
        default_factory=list,
        description="The quiz questions",
    )
    created_at: datetime = Field(..., description="When the quiz was created")
    generated_at: datetime | None = Field(
        default=None,
        description="When the quiz finished generating",
    )
    # Nullable on purpose: pre-existing quizzes saved before versioning
    # was introduced remain ``None``, which downstream code reads as v1
    # (the original, position-skewed corpus).
    version: str | None = Field(
        default=None,
        description="Corpus version (e.g. 'v2'). None = legacy v1.",
    )


class QuizSubmission(BaseModel):
    """A participant's submission for a quiz.

    Two scoring schemes are persisted side-by-side:

    * ``total_correct`` counts hits only (wrong = 0). ``score_percentage``
      mirrors that as a 0–100 share for admin views.
    * ``score_penalty`` is the +1/0/−1 net score (correct − wrong, abstain
      neutral) that participants are explicitly told about in the quiz
      intro. ``total_wrong`` is the matching wrong-pick count (abstain not
      included).
    """

    model_config = {"extra": "ignore"}

    quiz_id: str = Field(..., description="ID of the quiz being submitted")
    answers: list[QuizAnswer] = Field(..., description="The participant's answers")
    submitted_at: datetime = Field(..., description="When the quiz was submitted")
    total_correct: int = Field(..., description="Number of correct answers (wrong = 0).")
    total_wrong: int = Field(
        default=0,
        description=(
            "Number of wrong, non-abstain answers. Defaults to 0 for "
            "submissions written before the dual-scoring change."
        ),
    )
    total_questions: int = Field(..., description="Total number of questions")
    score_percentage: float = Field(
        ...,
        description="Score as a percentage (0-100). Abstain counts as wrong.",
    )
    score_penalty: int = Field(
        default=0,
        description=(
            "Net +1/0/−1 score: correct − wrong (abstain neutral). "
            "Defaults to 0 for legacy submissions; recompute from "
            "``answers`` if you need it on those."
        ),
    )


def grade_answer(question: QuizQuestion, selected_index: int) -> bool:
    """Return ``True`` iff the selected option matches the correct one.

    Abstain (``selected_index == -1``) is always wrong.
    """
    return selected_index == question.correct_index


def calculate_quiz_score(
    questions: list[QuizQuestion],
    answers: list[QuizAnswer],
) -> tuple[int, int, int, float, int]:
    """Calculate both scoring schemes for one quiz submission.

    Returns:
        ``(correct, wrong, total, percentage, penalty)``. ``wrong`` excludes
        abstain picks (``selected_index == -1``); ``penalty`` is
        ``correct − wrong``.
    """
    total = len(questions)
    if not questions:
        return 0, 0, 0, 0.0, 0

    question_map = {q.id: q for q in questions}
    correct = 0
    wrong = 0
    for a in answers:
        if a.question_id not in question_map:
            continue
        if a.is_correct:
            correct += 1
        elif a.selected_index != -1:
            wrong += 1
    percentage = (correct / total) * 100 if total > 0 else 0.0
    penalty = correct - wrong
    return correct, wrong, total, percentage, penalty
