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
    group_counts: dict[Literal["A1", "A2", "B1", "B2"], int] = Field(
        ...,
        description="Number of sessions per group",
    )


class SessionSummary(BaseModel):
    """Summary of a session for admin listing."""

    id: str
    state: StudyState
    group: Literal["A1", "A2", "B1", "B2"]
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
    by_group: dict[Literal["A1", "A2", "B1", "B2"], int] = Field(
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
    group: Literal["A1", "A2", "B1", "B2"]
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


class MailsShortRequest(BaseModel):
    """MAILS-Short responses (4 items, 0-10 scale).

    One item per subscale: item1 Detect AI, item5 AI Ethics, item7 Apply AI,
    item10 Understand AI. Item numbers preserved from the original 10-item
    scale for traceability.
    """

    item1: int = Field(..., ge=0, le=10)
    item5: int = Field(..., ge=0, le=10)
    item7: int = Field(..., ge=0, le=10)
    item10: int = Field(..., ge=0, le=10)


class LiteracyRequest(BaseModel):
    """Request for submitting literacy data."""

    mails_short: MailsShortRequest = Field(
        ...,
        description="MAILS-Short responses (4 items, 0-10 self-assessment)",
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
    next_state: StudyState = Field(
        ...,
        description="The state after this task ends (for reference)",
    )


class ManipulationChecksRequest(BaseModel):
    """Manipulation check responses (1-5 Likert scale)."""

    depth: int = Field(..., ge=1, le=5, description="Information detail adequacy (1-5)")
    clarity: int = Field(..., ge=1, le=5, description="Information clarity (1-5)")
    task_clarity: int = Field(..., ge=1, le=5, description="Task clarity (1-5)")
    technical: int = Field(..., ge=1, le=5, description="Technical function (1-5)")


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


class QuestionnaireRequest(BaseModel):
    """Request for submitting questionnaire (Cognitive Load + UEQ-S + Manipulation Checks)."""

    cognitive_load: CognitiveLoadRequest = Field(
        ...,
        description="Cognitive Load responses (Klepsch et al., 2017)",
    )
    ueq_s: dict = Field(
        ...,
        description="UEQ-S responses",
    )
    manipulation_checks: ManipulationChecksRequest = Field(
        ...,
        description="Manipulation check responses",
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
    error_message: str | None = None


class QuizForParticipant(BaseModel):
    """Quiz without correct answers for participant."""

    quiz_id: str
    questions: list[QuizQuestionForParticipant]


class QuizAnswerRequest(BaseModel):
    """A single quiz answer from participant.

    ``selected_index`` 0-3 are content choices; 4 is "Weiß ich nicht".
    """

    question_id: str
    selected_index: int = Field(..., ge=0, le=4)
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
