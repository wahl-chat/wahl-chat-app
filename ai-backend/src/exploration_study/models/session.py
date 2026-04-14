"""Study session model for participant sessions."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.exploration_study.models.state import StudyState


class ManipulationChecks(BaseModel):
    """Manipulation check responses for a condition (1-5 Likert scale)."""

    depth: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Die Informationen waren ausreichend detailliert. (1-5)",
    )
    clarity: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Die Informationen waren verständlich dargestellt. (1-5)",
    )
    task_clarity: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Mir war klar, was ich tun sollte. (1-5)",
    )
    technical: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Das System funktionierte ohne technische Probleme. (1-5)",
    )


class SystemType(str, Enum):
    """The type of system (condition) for a task."""

    GUIDED = "guided"
    BASELINE = "baseline"


class ConditionData(BaseModel):
    """Data for a single condition (task) within a session."""

    system: SystemType = Field(..., description="Which system to use for this task")
    topic: str = Field(..., description="The topic for this task")
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
    questionnaire_submitted_at: datetime | None = Field(
        default=None,
        description="When the questionnaire was submitted",
    )
    nasa_tlx: dict | None = Field(
        default=None,
        description="NASA-TLX responses",
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
    manipulation_checks: ManipulationChecks | None = Field(
        default=None,
        description="Manipulation check responses",
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


class MailsShortData(BaseModel):
    """
    Meta-AI Literacy Scale – Short Version (MAILS-Short).

    Koch, Carolus, et al., 2024. 10 items, 0-10 self-assessment scale
    (0 = gar nicht ausgeprägt, 10 = (nahezu) perfekt ausgeprägt).
    """

    item1: int | None = Field(default=None, ge=0, le=10)
    item2: int | None = Field(default=None, ge=0, le=10)
    item3: int | None = Field(default=None, ge=0, le=10)
    item4: int | None = Field(default=None, ge=0, le=10)
    item5: int | None = Field(default=None, ge=0, le=10)
    item6: int | None = Field(default=None, ge=0, le=10)
    item7: int | None = Field(default=None, ge=0, le=10)
    item8: int | None = Field(default=None, ge=0, le=10)
    item9: int | None = Field(default=None, ge=0, le=10)
    item10: int | None = Field(default=None, ge=0, le=10)


class LiteracyData(BaseModel):
    """Digital/AI literacy and political knowledge data from screening questionnaire."""

    # AI literacy: MAILS-Short (Koch, Carolus, et al., 2024)
    mails_short: MailsShortData | None = Field(
        default=None,
        description="MAILS-Short responses (10 items, 0-10 self-assessment)",
    )

    news_consumption: list[str] | None = Field(
        default=None,
        description="News consumption sources (online, tv, newspaper, social_media, radio)",
    )

    @field_validator("news_consumption", mode="before")
    @classmethod
    def ensure_list(cls, v: str | list[str] | None) -> list[str] | None:
        """Handle legacy data where news_consumption was stored as a string."""
        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        return v


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
    literacy: LiteracyData = Field(
        default_factory=LiteracyData,
        description="Literacy screening data",
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
    group: Literal["A1", "A2", "B1", "B2"] = Field(
        ...,
        description="Between-subjects group (A=guided, B=baseline; 1/2=topic counterbalance)",
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

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


# Hardcoded topics for the study
STUDY_TOPICS = ["soziale-gerechtigkeit", "klimaschutz"]


def get_condition_for_group(
    group: Literal["A1", "A2", "B1", "B2"],
    topics: list[str] | None = None,
) -> ConditionData:
    """
    Create condition data based on group assignment.

    Between-subjects A/B design with topic counterbalancing:
    - Group A1: Guided + Topic1
    - Group A2: Guided + Topic2
    - Group B1: Baseline + Topic1
    - Group B2: Baseline + Topic2

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
    }
    return mapping[group]
