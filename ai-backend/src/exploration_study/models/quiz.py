"""Quiz models for knowledge retention measurement."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QuizStatus(str, Enum):
    """Status of quiz generation."""

    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question."""

    id: str = Field(..., description="Unique question identifier")
    question: str = Field(..., description="The question text")
    options: list[str] = Field(
        ...,
        description="List of answer options (4 options)",
        min_length=4,
        max_length=4,
    )
    correct_index: int = Field(
        ...,
        description="Index of the correct answer (0-3)",
        ge=0,
        le=3,
    )
    party: str = Field(..., description="The party this question is about")
    topic: str = Field(..., description="The topic this question covers")
    source_excerpt: str | None = Field(
        default=None,
        description="Excerpt from chat that this question is based on",
    )


class QuizAnswer(BaseModel):
    """A participant's answer to a quiz question."""

    question_id: str = Field(..., description="ID of the question being answered")
    selected_index: int = Field(
        ...,
        description="Index of the selected answer (0-3)",
        ge=0,
        le=3,
    )
    is_correct: bool = Field(..., description="Whether the answer was correct")
    response_time_ms: int | None = Field(
        default=None,
        description="Time taken to answer in milliseconds",
    )


class Quiz(BaseModel):
    """A complete quiz generated for a task."""

    id: str = Field(..., description="Unique quiz identifier")
    session_id: str = Field(..., description="The session this quiz belongs to")
    condition_num: int = Field(
        ...,
        description="The condition number (1 or 2)",
        ge=1,
        le=2,
    )
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
    error_message: str | None = Field(
        default=None,
        description="Error message if generation failed",
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class QuizSubmission(BaseModel):
    """A participant's submission for a quiz."""

    quiz_id: str = Field(..., description="ID of the quiz being submitted")
    answers: list[QuizAnswer] = Field(..., description="The participant's answers")
    submitted_at: datetime = Field(..., description="When the quiz was submitted")
    total_correct: int = Field(..., description="Number of correct answers")
    total_questions: int = Field(..., description="Total number of questions")
    score_percentage: float = Field(..., description="Score as a percentage (0-100)")


def calculate_quiz_score(
    questions: list[QuizQuestion],
    answers: list[QuizAnswer],
) -> tuple[int, int, float]:
    """
    Calculate quiz score from questions and answers.

    Returns:
        Tuple of (correct_count, total_count, percentage)
    """
    if not questions:
        return 0, 0, 0.0

    question_map = {q.id: q for q in questions}
    correct = sum(
        1
        for a in answers
        if a.question_id in question_map
        and a.selected_index == question_map[a.question_id].correct_index
    )
    total = len(questions)
    percentage = (correct / total) * 100 if total > 0 else 0.0

    return correct, total, percentage
