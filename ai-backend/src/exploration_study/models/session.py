"""Study session model for participant sessions."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.exploration_study.models.state import StudyState

# Type alias for task keys in conditions dict
TaskKey = Literal["1", "2"]


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
    recall_text: str | None = Field(
        default=None,
        description="Free recall text from participant",
    )
    recall_submitted_at: datetime | None = Field(
        default=None,
        description="When the recall was submitted",
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


class LiteracyData(BaseModel):
    """Digital/AI literacy and political knowledge data from screening questionnaire."""

    # AI literacy fields
    ai_familiarity: int | None = Field(
        default=None,
        ge=1,
        le=7,
        description="Familiarity with AI chatbots (1-7)",
    )
    chatbot_usage: str | None = Field(
        default=None,
        description="How often they use chatbots (never, rarely, monthly, weekly, daily)",
    )
    news_consumption: list[str] | None = Field(
        default=None,
        description="News consumption sources (online, tv, newspaper, social_media, radio)",
    )

    # Political literacy quiz answers (3 questions)
    political_literacy_answers: dict[str, str] | None = Field(
        default=None,
        description="Answers to political literacy questions (lit_1, lit_2, lit_3)",
    )
    political_literacy_score: int | None = Field(
        default=None,
        ge=0,
        le=3,
        description="Score on political literacy quiz (0-3)",
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


class PreferencesData(BaseModel):
    """Final preferences data comparing the two systems."""

    # Overall preference (plan: pref_overall)
    preferred_system: Literal["guided", "baseline", "no_preference"] | None = Field(
        default=None,
        description="Which system preferred overall",
    )

    # Why preferred (plan: pref_why)
    preference_reason: str | None = Field(
        default=None,
        description="Why they preferred that system",
    )

    # Better for overview (plan: pref_overview)
    better_for_overview: Literal["guided", "baseline", "no_difference"] | None = Field(
        default=None,
        description="Which system was better for getting an overview",
    )

    # Better for details (plan: pref_detail)
    better_for_details: Literal["guided", "baseline", "no_difference"] | None = Field(
        default=None,
        description="Which system was better for understanding details",
    )

    # Optional feedback (plan: feedback)
    additional_feedback: str | None = Field(
        default=None,
        description="Any other comments",
    )


class RecallData(BaseModel):
    """Recall text and scoring for a condition."""

    text: str = Field(..., description="The free recall text from participant")
    submitted_at: datetime = Field(..., description="When the recall was submitted")
    # Scoring can be added later by analysis
    score: float | None = Field(
        default=None,
        description="Recall score (set during analysis)",
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
    literacy: LiteracyData = Field(
        default_factory=LiteracyData,
        description="Literacy screening data",
    )
    preferences: PreferencesData = Field(
        default_factory=PreferencesData,
        description="Final preferences data",
    )


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
    group: Literal["A", "B", "C", "D"] = Field(
        ...,
        description="Counterbalancing group for 2x2 Latin square design",
    )
    conditions: dict[TaskKey, ConditionData] = Field(
        ...,
        description="Condition data for each task (1 and 2)",
    )
    participant_data: ParticipantData = Field(
        default_factory=ParticipantData,
        description="Data collected from the participant",
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


def get_conditions_for_group(
    group: Literal["A", "B", "C", "D"],
    topics: list[str] | None = None,
) -> dict[TaskKey, ConditionData]:
    """
    Create condition data based on group assignment.

    2x2 Latin square design counterbalancing mode order and topic order:
    - Group A: Task 1 = Guided + Topic1, Task 2 = Baseline + Topic2
    - Group B: Task 1 = Baseline + Topic1, Task 2 = Guided + Topic2
    - Group C: Task 1 = Guided + Topic2, Task 2 = Baseline + Topic1
    - Group D: Task 1 = Baseline + Topic2, Task 2 = Guided + Topic1

    Args:
        group: The counterbalancing group (A, B, C, or D)
        topics: Optional list of topics (uses STUDY_TOPICS if not provided)
    """
    # Use hardcoded topics if not provided
    topic_list = topics if topics else STUDY_TOPICS
    if len(topic_list) < 2:
        raise ValueError("At least 2 topics required for the study")

    topic1, topic2 = topic_list[0], topic_list[1]

    if group == "A":
        # Guided first, Topic1 first
        return {
            "1": ConditionData(system=SystemType.GUIDED, topic=topic1),
            "2": ConditionData(system=SystemType.BASELINE, topic=topic2),
        }
    elif group == "B":
        # Baseline first, Topic1 first
        return {
            "1": ConditionData(system=SystemType.BASELINE, topic=topic1),
            "2": ConditionData(system=SystemType.GUIDED, topic=topic2),
        }
    elif group == "C":
        # Guided first, Topic2 first
        return {
            "1": ConditionData(system=SystemType.GUIDED, topic=topic2),
            "2": ConditionData(system=SystemType.BASELINE, topic=topic1),
        }
    else:  # group == "D"
        # Baseline first, Topic2 first
        return {
            "1": ConditionData(system=SystemType.BASELINE, topic=topic2),
            "2": ConditionData(system=SystemType.GUIDED, topic=topic1),
        }
