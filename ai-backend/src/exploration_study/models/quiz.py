"""Quiz models for knowledge retention measurement."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QuizStatus(str, Enum):
    """Status of quiz generation."""

    PENDING = "pending"
    READY = "ready"


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question.

    Options 0-3 are content choices from the corpus. Option 4 is always
    ``"Weiß ich nicht"``, appended by the sampler. ``correct_index`` is
    always 0-3 — don't-know is never the correct answer, only a valid
    response.
    """

    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The question text")
    options: list[str] = Field(
        ...,
        description="Answer options (4 content + 1 'Weiß ich nicht')",
        min_length=5,
        max_length=5,
    )
    correct_index: int = Field(
        ...,
        description="Index of the correct answer (0-3); never 4 (don't-know)",
        ge=0,
        le=3,
    )
    is_overlap_question: bool = Field(
        default=False,
        description="True if the question targets a known cross-party overlap.",
    )
    partial_credit_indices: list[int] = Field(
        default_factory=list,
        description=(
            "Answer indices (0-3) that earn 0.5 partial credit instead of 0. "
            "Typically the individual-party options on an overlap question "
            "whose correct answer is 'Mehrere der genannten Parteien'."
        ),
    )
    topic: str = Field(..., description="The topic this question covers")


class QuizAnswer(BaseModel):
    """A participant's answer to a quiz question.

    ``selected_index`` 0-3 are content choices; 4 is "Weiß ich nicht".
    ``credit`` captures partial-credit scoring: 1.0 for the fully correct
    answer, 0.5 for an option listed in the question's
    ``partial_credit_indices`` (typically picking one of two parties when
    the correct answer is "Mehrere"), 0.0 otherwise.
    ``is_correct`` is True only when ``credit == 1.0`` (fully correct).
    """

    question_id: str = Field(..., description="ID of the question being answered")
    selected_index: int = Field(
        ...,
        description="Index of the selected answer (0-4; 4 = don't-know)",
        ge=0,
        le=4,
    )
    is_correct: bool = Field(
        ...,
        description="True only when fully correct (credit == 1.0).",
    )
    credit: float = Field(
        default=0.0,
        description="Earned credit: 1.0 fully correct, 0.5 partial, 0.0 wrong.",
        ge=0.0,
        le=1.0,
    )
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


class QuizSubmission(BaseModel):
    """A participant's submission for a quiz."""

    quiz_id: str = Field(..., description="ID of the quiz being submitted")
    answers: list[QuizAnswer] = Field(..., description="The participant's answers")
    submitted_at: datetime = Field(..., description="When the quiz was submitted")
    total_correct: int = Field(
        ...,
        description="Number of fully correct answers (credit == 1.0).",
    )
    total_credit: float = Field(
        ...,
        description="Sum of earned credit including partial credit (0.5 each).",
    )
    total_questions: int = Field(..., description="Total number of questions")
    score_percentage: float = Field(
        ...,
        description="Credit-based score as a percentage (0-100).",
    )


def grade_answer(
    question: QuizQuestion,
    selected_index: int,
) -> tuple[bool, float]:
    """Return ``(is_correct, credit)`` for a single answer."""
    if selected_index == question.correct_index:
        return True, 1.0
    if selected_index in question.partial_credit_indices:
        return False, 0.5
    return False, 0.0


def calculate_quiz_score(
    questions: list[QuizQuestion],
    answers: list[QuizAnswer],
) -> tuple[int, float, int, float]:
    """
    Calculate quiz score from questions and answers with partial credit.

    Returns:
        Tuple of (fully_correct_count, total_credit, total_questions, percentage).
        ``percentage`` is credit-based (total_credit / total_questions * 100).
    """
    if not questions:
        return 0, 0.0, 0, 0.0

    question_map = {q.id: q for q in questions}
    fully_correct = 0
    total_credit = 0.0
    for a in answers:
        question = question_map.get(a.question_id)
        if question is None:
            continue
        total_credit += a.credit
        if a.is_correct:
            fully_correct += 1
    total = len(questions)
    percentage = (total_credit / total) * 100 if total > 0 else 0.0
    return fully_correct, total_credit, total, percentage
