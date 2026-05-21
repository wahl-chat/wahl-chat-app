"""Study session model for participant sessions."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.exploration_study.models.state import StudyState


class CognitiveLoadData(BaseModel):
    """
    Cognitive load responses (Klepsch, Schmitz & Seufert, 2017,
    Frontiers in Psychology, 8, Article 1997).

    Naive-rating questionnaire (final version, Table 3). 7 items, 7-point
    Likert (1 = "Komplett falsch" / 7 = "Komplett richtig"). Optional GCL*
    item omitted (no germane-load manipulation between conditions).
    "Lerneinheit" → "Aufgabe" in cl_gcl_2 to match task framing
    (declared adaptation).

    Subscale means computed in analysis as mean(cl_icl_1, cl_icl_2),
    mean(cl_ecl_1..3), mean(cl_gcl_1, cl_gcl_2). Storage stays flat.
    """

    cl_icl_1: int | None = Field(default=None, ge=1, le=7)
    cl_icl_2: int | None = Field(default=None, ge=1, le=7)
    cl_ecl_1: int | None = Field(default=None, ge=1, le=7)
    cl_ecl_2: int | None = Field(default=None, ge=1, le=7)
    cl_ecl_3: int | None = Field(default=None, ge=1, le=7)
    cl_gcl_1: int | None = Field(default=None, ge=1, le=7)
    cl_gcl_2: int | None = Field(default=None, ge=1, le=7)
    qualitative_feedback: str | None = Field(
        default=None,
        description=(
            "Optional free-text comment on perceived task load. Only collected "
            "in qualitative studies; None otherwise."
        ),
    )


class SystemType(str, Enum):
    """The type of system (condition) for a task."""

    GUIDED = "guided"
    BASELINE = "baseline"


class ConditionData(BaseModel):
    """Data for a single condition (task) within a session."""

    system: SystemType = Field(..., description="Which system to use for this task")
    topic: str = Field(..., description="The topic for this task")
    max_claims_per_party: int | None = Field(
        default=None,
        description=(
            "Optional cap on how many claims the baseline assistant may "
            "surface per party in a single response. None = no cap (free "
            "baseline, B groups). Set to 3 for the capped baseline arm "
            "(C groups). Ignored for guided sessions."
        ),
    )
    chat_id: str | None = Field(
        default=None,
        description="The guided exploration session ID once task starts",
    )
    started_at: datetime | None = Field(
        default=None,
        description="When the task was started",
    )
    ended_at: datetime | None = Field(
        default=None,
        description="When the task was ended",
    )
    first_finish_click_at: datetime | None = Field(
        default=None,
        description=(
            "When the user first clicked 'Aufgabe beenden' — recorded "
            "even if the 7-min lockout was still active and the click "
            "was swallowed by the frontend. Used to surface participants "
            "who tried to bail out before the minimum task duration."
        ),
    )
    questionnaire_submitted_at: datetime | None = Field(
        default=None,
        description="When the questionnaire was submitted",
    )
    cognitive_load: CognitiveLoadData | None = Field(
        default=None,
        description="Cognitive Load responses (Klepsch et al., 2017)",
    )
    attention_check: int | None = Field(
        default=None,
        ge=1,
        le=7,
        description=(
            "Embedded attention-check response from the Cognitive Load block "
            "(1-7). Expected value: 2. Used for participant-quality filtering "
            "in analysis; exclusion criterion is not enforced in-form."
        ),
    )
    ueq_s: dict | None = Field(
        default=None,
        description="UEQ-S responses",
    )
    quiz_id: str | None = Field(
        default=None,
        description="ID of the generated quiz",
    )
    quiz_submitted_at: datetime | None = Field(
        default=None,
        description="When the quiz was submitted",
    )
    positions_encountered: list[str] = Field(
        default_factory=list,
        description=(
            "Master position ids that the LLM cited in responses during "
            "the task. Dedup-appended as the participant interacts. Used "
            "as the Information Exposure mediator (M1) in analysis."
        ),
    )


class DemographicsData(BaseModel):
    """Demographics data collected from participant."""

    age_range: str | None = Field(default=None, description="Age range bucket")
    gender: str | None = Field(default=None, description="Gender identity")
    education: str | None = Field(default=None, description="Education level")
    political_interest: int | None = Field(
        default=None,
        ge=1,
        le=7,
        description="Political interest (1-7 scale)",
    )
    ai_chat_usage_frequency: str | None = Field(
        default=None,
        description=(
            "How often the participant uses AI chat applications like "
            "ChatGPT or Claude. One of: never, less_than_monthly, "
            "several_times_per_month, several_times_per_week, almost_daily."
        ),
    )
    net_promoter_score: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Net Promoter Score: likelihood to recommend (0-10 scale)",
    )


class ParticipantData(BaseModel):
    """All participant-provided data aggregated."""

    consent_given: bool = Field(default=False, description="Whether consent was given")
    consent_timestamp: datetime | None = Field(
        default=None,
        description="When consent was given",
    )
    demographics: DemographicsData = Field(
        default_factory=DemographicsData,
        description="Demographics data",
    )
    feedback: str | None = Field(
        default=None,
        description="Optional open-ended feedback from participant",
    )


class ProlificData(BaseModel):
    """Prolific tracking identifiers captured from the invitation URL."""

    pid: str | None = Field(default=None, description="Prolific participant ID")
    study_id: str | None = Field(default=None, description="Prolific study ID")
    session_id: str | None = Field(default=None, description="Prolific session ID")


class StudySession(BaseModel):
    """
    A participant session for a study.

    Sessions are pre-created by admins and assigned to participants.
    The session ID serves as the access token (no authentication required).
    """

    id: str = Field(..., description="Unique session identifier (also access token)")
    study_id: str = Field(..., description="The study this session belongs to")
    state: StudyState = Field(
        default=StudyState.CONSENT,
        description="Current step in the study flow",
    )
    group: Literal["A1", "A2", "B1", "B2", "C1", "C2"] = Field(
        ...,
        description=(
            "Between-subjects group (A=guided, B=baseline-free, "
            "C=baseline-capped; 1/2=topic counterbalance)"
        ),
    )
    condition: ConditionData = Field(
        ...,
        description="Condition data for the single task",
    )
    participant_data: ParticipantData = Field(
        default_factory=ParticipantData,
        description="Data collected from the participant",
    )
    prolific: ProlificData | None = Field(
        default=None,
        description="Prolific tracking identifiers (set at session creation)",
    )
    created_at: datetime = Field(..., description="When the session was created")
    started_at: datetime | None = Field(
        default=None,
        description="When the participant started (consent)",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="When the participant completed the study",
    )
    prolific_redirected_at: datetime | None = Field(
        default=None,
        description=(
            "When the participant was redirected back to Prolific via the "
            "post-study redirect endpoint. Set on the first redirect call; "
            "subsequent calls re-redirect but do not overwrite the timestamp."
        ),
    )
    manually_completed: bool = Field(
        default=False,
        description=(
            "True if an admin force-completed this session rather than the "
            "participant submitting demographics (e.g. someone who finished "
            "the study but could not complete the demographics step). Keeps "
            "admin completions distinguishable from genuine completions in "
            "analysis; such sessions have empty demographics."
        ),
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


# Hardcoded topics for the study
STUDY_TOPICS = ["soziale-gerechtigkeit", "klimaschutz"]


BASELINE_CAPPED_CLAIMS_PER_PARTY = 3


def get_condition_for_group(
    group: Literal["A1", "A2", "B1", "B2", "C1", "C2"],
    topics: list[str] | None = None,
) -> ConditionData:
    """
    Create condition data based on group assignment.

    Between-subjects design with topic counterbalancing:
    - Group A1: Guided          + Topic1
    - Group A2: Guided          + Topic2
    - Group B1: Baseline (free) + Topic1
    - Group B2: Baseline (free) + Topic2
    - Group C1: Baseline capped + Topic1 (≤3 claims/party/turn)
    - Group C2: Baseline capped + Topic2 (≤3 claims/party/turn)

    Args:
        group: The between-subjects group
        topics: Optional list of topics (uses STUDY_TOPICS if not provided)
    """
    topic_list = topics if topics else STUDY_TOPICS
    if len(topic_list) < 2:
        raise ValueError("At least 2 topics required for the study")

    topic1, topic2 = topic_list[0], topic_list[1]

    mapping: dict[str, ConditionData] = {
        "A1": ConditionData(system=SystemType.GUIDED, topic=topic1),
        "A2": ConditionData(system=SystemType.GUIDED, topic=topic2),
        "B1": ConditionData(system=SystemType.BASELINE, topic=topic1),
        "B2": ConditionData(system=SystemType.BASELINE, topic=topic2),
        "C1": ConditionData(
            system=SystemType.BASELINE,
            topic=topic1,
            max_claims_per_party=BASELINE_CAPPED_CLAIMS_PER_PARTY,
        ),
        "C2": ConditionData(
            system=SystemType.BASELINE,
            topic=topic2,
            max_claims_per_party=BASELINE_CAPPED_CLAIMS_PER_PARTY,
        ),
    }
    return mapping[group]
