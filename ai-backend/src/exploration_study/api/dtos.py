"""Request and response DTOs for exploration study API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.exploration_study.models.quiz import QuizQuestion, QuizStatus
from src.exploration_study.models.session import SystemType
from src.exploration_study.models.state import StudyState
from src.exploration_study.models.study import StudyStatus


# =============================================================================
# Admin DTOs
# =============================================================================


class CreateStudyRequest(BaseModel):
    """Request body for creating a new study."""

    name: str = Field(..., description="Human-readable study name")
    context_id: str = Field(..., description="Context ID for fake parties")
    topics: list[str] = Field(
        ...,
        description="List of topics for the study tasks",
        min_length=2,
    )
    task_duration_seconds: int = Field(
        default=600,
        description="Duration in seconds for each task",
        ge=60,
    )
    parties: list[str] = Field(
        default=["Merkur", "Venus", "Mars", "Jupiter", "Saturn"],
        description="List of party names for the fake context",
    )


class CreateStudyResponse(BaseModel):
    """Response for study creation."""

    id: str = Field(..., description="Unique study ID")
    name: str = Field(..., description="Study name")
    status: StudyStatus = Field(..., description="Study status")
    created_at: datetime = Field(..., description="Creation timestamp")


class StudyResponse(BaseModel):
    """Full study response."""

    id: str
    name: str
    status: StudyStatus
    context_id: str
    topics: list[str]
    task_duration_seconds: int
    parties: list[str]
    created_at: datetime
    updated_at: datetime
    session_count: int = Field(default=0, description="Number of sessions")


class UpdateStudyRequest(BaseModel):
    """Request for updating a study."""

    name: str | None = Field(default=None, description="New study name")
    status: StudyStatus | None = Field(default=None, description="New status")


class CreateSessionsRequest(BaseModel):
    """Request for creating multiple participant sessions."""

    count: int = Field(
        ...,
        description="Number of sessions to create",
        ge=1,
        le=100,
    )


class CreateSessionsResponse(BaseModel):
    """Response for session creation."""

    session_ids: list[str] = Field(..., description="Created session IDs")
    group_counts: dict[Literal["A", "B", "C", "D"], int] = Field(
        ...,
        description="Number of sessions per group",
    )


class SessionSummary(BaseModel):
    """Summary of a session for admin listing."""

    id: str
    state: StudyState
    group: Literal["A", "B", "C", "D"]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ListSessionsResponse(BaseModel):
    """Response for listing sessions."""

    sessions: list[SessionSummary]
    total: int
    by_state: dict[str, int] = Field(
        default_factory=dict,
        description="Count of sessions by state",
    )
    by_group: dict[Literal["A", "B", "C", "D"], int] = Field(
        default_factory=dict,
        description="Count of sessions by group",
    )


# =============================================================================
# Participant DTOs
# =============================================================================


class SessionStateResponse(BaseModel):
    """Current session state for participant."""

    session_id: str
    state: StudyState
    group: Literal["A", "B", "C", "D"]
    current_condition: SystemType | None = Field(
        default=None,
        description="Current condition type ('guided' or 'baseline') if in task",
    )
    current_system: SystemType | None = Field(
        default=None,
        description="Current system type if in task",
    )
    current_topic: str | None = Field(
        default=None,
        description="Current topic if in task",
    )
    chat_ids: dict[str, str | None] = Field(
        default_factory=dict,
        description="Chat session IDs for each task, keyed by task number ('1', '2')",
    )
    task_duration_seconds: int = Field(
        default=600,
        description="Task duration in seconds",
    )


class ConsentRequest(BaseModel):
    """Request for submitting consent."""

    consent_given: bool = Field(
        ...,
        description="Whether consent was given",
    )


class DemographicsRequest(BaseModel):
    """Request for submitting demographics."""

    age_range: str = Field(..., description="Age range buckGive me et")
    gender: str = Field(..., description="Gender identity")
    education: str = Field(..., description="Education level")
    political_interest: int = Field(
        ...,
        ge=1,
        le=7,
        description="Political interest (1-7)",
    )


class LiteracyRequest(BaseModel):
    """Request for submitting literacy data."""

    # AI literacy
    ai_familiarity: int = Field(
        ...,
        ge=1,
        le=7,
        description="Familiarity with AI chatbots (1-7)",
    )
    chatbot_usage: str = Field(
        ...,
        description="How often they use chatbots (never, rarely, monthly, weekly, daily)",
    )
    news_consumption: list[str] = Field(
        ...,
        description="News consumption sources (online, tv, newspaper, social_media, radio)",
    )

    # Political literacy quiz answers
    political_literacy_answers: dict[str, str] = Field(
        ...,
        description="Answers to political literacy questions (lit_1, lit_2, lit_3)",
    )


class StartTaskResponse(BaseModel):
    """Response when starting a task."""

    condition_num: int
    system: SystemType
    topic: str
    chat_id: str
    stream_url: str = Field(
        ...,
        description="URL for the SSE stream",
    )
    duration_seconds: int
    next_state: StudyState = Field(
        ...,
        description="The state after this task ends (for reference)",
    )


class EndTaskRequest(BaseModel):
    """Request for ending a task."""

    pass  # No body needed, just POST to signal task end


class ManipulationChecksRequest(BaseModel):
    """Manipulation check responses (1-5 Likert scale)."""

    depth: int = Field(..., ge=1, le=5, description="Information detail adequacy (1-5)")
    clarity: int = Field(..., ge=1, le=5, description="Information clarity (1-5)")
    task_clarity: int = Field(..., ge=1, le=5, description="Task clarity (1-5)")
    technical: int = Field(..., ge=1, le=5, description="Technical function (1-5)")


class QuestionnaireRequest(BaseModel):
    """Request for submitting questionnaire (NASA-TLX + UEQ-S + Manipulation Checks)."""

    nasa_tlx: dict = Field(
        ...,
        description="NASA-TLX responses",
    )
    ueq_s: dict = Field(
        ...,
        description="UEQ-S responses",
    )
    manipulation_checks: ManipulationChecksRequest = Field(
        ...,
        description="Manipulation check responses",
    )


class RecallRequest(BaseModel):
    """Request for submitting free recall."""

    text: str = Field(
        ...,
        description="Free recall text from participant",
        max_length=10000,
    )


class QuizStatusResponse(BaseModel):
    """Response for quiz status check."""

    status: QuizStatus
    is_ready: bool
    questions: list[QuizQuestion] | None = Field(
        default=None,
        description="Questions if ready (without correct answers for participant)",
    )
    error_message: str | None = None


class QuizQuestionForParticipant(BaseModel):
    """Quiz question without correct answer for participant view."""

    id: str
    question: str
    options: list[str]
    party: str


class QuizForParticipant(BaseModel):
    """Quiz without correct answers for participant."""

    quiz_id: str
    questions: list[QuizQuestionForParticipant]


class QuizAnswerRequest(BaseModel):
    """A single quiz answer from participant."""

    question_id: str
    selected_index: int = Field(..., ge=0, le=3)
    response_time_ms: int | None = None


class QuizSubmissionRequest(BaseModel):
    """Request for submitting quiz answers."""

    answers: list[QuizAnswerRequest]


class QuizResultResponse(BaseModel):
    """Response after quiz submission."""

    total_correct: int
    total_questions: int
    score_percentage: float
    next_state: StudyState = Field(
        ...,
        description="The next state after quiz submission",
    )


class PreferencesRequest(BaseModel):
    """Request for submitting final preferences."""

    # Overall preference (plan: pref_overall)
    preferred_system: Literal["guided", "baseline", "no_preference"] = Field(
        ...,
        description="Which system preferred overall",
    )

    # Why preferred (plan: pref_why)
    preference_reason: str | None = Field(
        default=None,
        description="Why they preferred that system",
    )

    # Better for overview (plan: pref_overview)
    better_for_overview: Literal["guided", "baseline", "no_difference"] = Field(
        ...,
        description="Which system was better for getting an overview",
    )

    # Better for details (plan: pref_detail)
    better_for_details: Literal["guided", "baseline", "no_difference"] = Field(
        ...,
        description="Which system was better for understanding details",
    )

    # Optional feedback (plan: feedback)
    additional_feedback: str | None = Field(
        default=None,
        description="Any other comments",
    )


class StateTransitionResponse(BaseModel):
    """Response for successful state transition."""

    previous_state: StudyState
    current_state: StudyState
    message: str = Field(default="Success")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
