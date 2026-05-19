"""Request and response DTOs for exploration study API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.exploration_study.models.quiz import QuizStatus
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
        default=["Venus", "Mars", "Saturn"],
        description="List of party names for the fake context",
    )
    study_type: Literal["quantitative", "qualitative"] = Field(
        default="quantitative",
        description=(
            "Whether the study is quantitative or qualitative. Qualitative "
            "studies render optional free-text fields on the questionnaires."
        ),
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
    study_type: Literal["quantitative", "qualitative"] = Field(
        default="quantitative",
        description="Whether the study is quantitative or qualitative",
    )
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
    group_counts: dict[Literal["A1", "A2", "B1", "B2", "C1", "C2"], int] = Field(
        ...,
        description="Number of sessions per group",
    )


class SessionSummary(BaseModel):
    """Summary of a session for admin listing."""

    id: str
    state: StudyState
    group: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
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
    by_group: dict[Literal["A1", "A2", "B1", "B2", "C1", "C2"], int] = Field(
        default_factory=dict,
        description="Count of sessions by group",
    )


# =============================================================================
# Participant DTOs
# =============================================================================


class CreateSessionRequest(BaseModel):
    """Request body for self-serve session creation."""

    prolific_pid: str | None = Field(
        default=None,
        description="Prolific participant ID (PROLIFIC_PID)",
        max_length=256,
    )
    prolific_study_id: str | None = Field(
        default=None,
        description="Prolific study ID (STUDY_ID)",
        max_length=256,
    )
    prolific_session_id: str | None = Field(
        default=None,
        description="Prolific session ID (SESSION_ID)",
        max_length=256,
    )


class CreateSessionResponse(BaseModel):
    """Response for self-serve session creation."""

    session_id: str = Field(..., description="Newly created session ID")
    state: StudyState = Field(..., description="Initial state of the session")


class SessionStateResponse(BaseModel):
    """Current session state for participant."""

    session_id: str
    state: StudyState
    group: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    current_condition: SystemType | None = Field(
        default=None,
        description="Condition type ('guided' or 'baseline')",
    )
    current_system: SystemType | None = Field(
        default=None,
        description="System type",
    )
    current_topic: str | None = Field(
        default=None,
        description="Topic for the task",
    )
    chat_id: str | None = Field(
        default=None,
        description="Chat session ID for the task",
    )
    task_duration_seconds: int = Field(
        default=600,
        description="Task duration in seconds",
    )
    task_started_at: datetime | None = Field(
        default=None,
        description=(
            "When the participant started the task (condition.started_at). "
            "Used by the frontend to keep the countdown timer in sync across "
            "page reloads. None until the task is started."
        ),
    )
    study_type: Literal["quantitative", "qualitative"] = Field(
        default="quantitative",
        description=(
            "Whether the study is quantitative or qualitative. In qualitative "
            "studies the frontend renders optional free-text fields on the "
            "questionnaires."
        ),
    )


class ConsentRequest(BaseModel):
    """Request for submitting consent."""

    consent_given: bool = Field(
        ...,
        description="Whether consent was given",
    )


class DemographicsRequest(BaseModel):
    """Request for submitting demographics."""

    age_range: str = Field(..., description="Age range bucket")
    gender: str = Field(..., description="Gender identity")
    education: str = Field(..., description="Education level")
    political_interest: int = Field(
        ...,
        ge=1,
        le=7,
        description="Political interest (1-7)",
    )
    ai_chat_usage_frequency: Literal[
        "never",
        "less_than_monthly",
        "several_times_per_month",
        "several_times_per_week",
        "almost_daily",
    ] = Field(
        ...,
        description=(
            "How often the participant uses AI chat applications like ChatGPT "
            "or Claude."
        ),
    )


class StartTaskResponse(BaseModel):
    """Response when starting a task."""

    system: SystemType
    topic: str
    chat_id: str
    stream_url: str = Field(
        ...,
        description="URL for the SSE stream",
    )
    duration_seconds: int
    task_started_at: datetime = Field(
        ...,
        description=(
            "When the task was started (condition.started_at). Returned so "
            "the frontend timer can anchor to a server timestamp instead of "
            "the moment the response is parsed."
        ),
    )
    next_state: StudyState = Field(
        ...,
        description="The state after this task ends (for reference)",
    )


class CognitiveLoadRequest(BaseModel):
    """
    Cognitive Load responses (Klepsch, Schmitz & Seufert, 2017).

    7 items on a 7-point Likert scale (1 = "Komplett falsch" /
    7 = "Komplett richtig"). Stored flat; subscale means computed in
    analysis.
    """

    cl_icl_1: int = Field(..., ge=1, le=7)
    cl_icl_2: int = Field(..., ge=1, le=7)
    cl_ecl_1: int = Field(..., ge=1, le=7)
    cl_ecl_2: int = Field(..., ge=1, le=7)
    cl_ecl_3: int = Field(..., ge=1, le=7)
    cl_gcl_1: int = Field(..., ge=1, le=7)
    cl_gcl_2: int = Field(..., ge=1, le=7)
    qualitative_feedback: str | None = Field(
        default=None,
        description=(
            "Optional free-text comment on perceived task load. Only collected "
            "in qualitative studies; absent otherwise."
        ),
    )


class QuestionnaireRequest(BaseModel):
    """Request for submitting questionnaire (Cognitive Load + UEQ-S)."""

    cognitive_load: CognitiveLoadRequest = Field(
        ...,
        description="Cognitive Load responses (Klepsch et al., 2017)",
    )
    attention_check: int = Field(
        ...,
        ge=1,
        le=7,
        description=(
            "Embedded attention-check item rendered inside the Cognitive Load "
            "block (1-7). Expected value: 2. Stored separately from CL data; "
            "exclusion is decided in analysis."
        ),
    )
    ueq_s: dict = Field(
        ...,
        description="UEQ-S responses",
    )


class QuizQuestionForParticipant(BaseModel):
    """Quiz question without correct answer for participant view."""

    id: str
    question: str
    options: list[str]


class QuizStatusResponse(BaseModel):
    """Response for quiz status check."""

    status: QuizStatus
    is_ready: bool
    questions: list[QuizQuestionForParticipant] | None = Field(
        default=None,
        description="Questions if ready (without correct answers for participant)",
    )


class QuizForParticipant(BaseModel):
    """Quiz without correct answers for participant."""

    quiz_id: str
    questions: list[QuizQuestionForParticipant]


class QuizAnswerRequest(BaseModel):
    """A single quiz answer from participant.

    ``selected_index`` is 0-2 for substantive options; ``-1`` indicates
    the "Weiß ich nicht" abstain (a UI affordance, not a stored option).
    """

    question_id: str
    selected_index: int = Field(..., ge=-1, le=2)
    response_time_ms: int | None = None


class QuizSubmissionRequest(BaseModel):
    """Request for submitting quiz answers."""

    answers: list[QuizAnswerRequest]


class QuizResultResponse(BaseModel):
    """Response after quiz submission."""

    total_correct: int = Field(..., description="Number of correct answers.")
    total_questions: int
    score_percentage: float = Field(
        ...,
        description="Score as a percentage (0-100). Abstain counts as wrong.",
    )
    next_state: StudyState = Field(
        ...,
        description="The next state after quiz submission",
    )


class QuizScoreResponse(BaseModel):
    """Persistent quiz score returned for the feedback page."""

    total_correct: int
    total_questions: int
    score_percentage: float


class FeedbackRequest(BaseModel):
    """Request for submitting optional feedback."""

    feedback: str | None = Field(
        default=None,
        description="Optional open-ended feedback",
        max_length=10000,
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


# =============================================================================
# Party claim source pages
# =============================================================================


class PartyClaimDto(BaseModel):
    """A single claim on a party source page.

    ``claim`` is the short declarative assertion; ``argument`` is the
    short "why" rationale surfaced when the participant digs deeper in
    the UI. The LLM sees both merged as one blob during retrieval — the
    split here is purely for authoring, UI display, and quiz focus.
    """

    id: str
    claim: str
    argument: str


class PartySubtopicDto(BaseModel):
    """A subtopic grouping within a topic."""

    slug: str
    label: str
    claims: list[PartyClaimDto]


class PartyTopicDto(BaseModel):
    """A topic grouping for a party's claims."""

    slug: str
    label: str
    subtopics: list[PartySubtopicDto]


class PartyClaimsResponse(BaseModel):
    """Full claim listing for one party, used by the study source page."""

    party_id: str
    party_name: str
    topics: list[PartyTopicDto]
