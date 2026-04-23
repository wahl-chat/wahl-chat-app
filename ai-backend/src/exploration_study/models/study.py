"""Study model for admin-created studies."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class StudyStatus(str, Enum):
    """Status of a study."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


# Hardcoded study configuration
STUDY_TOPICS = ["klimaschutz", "soziale-gerechtigkeit"]
STUDY_TOPIC_LABELS: dict[str, str] = {
    "klimaschutz": "Klimaschutz",
    "soziale-gerechtigkeit": "Soziale Gerechtigkeit",
}
# 10-minute task budget is the binding constraint: it's long enough for the
# guided condition to show structural benefit over chat, short enough to
# avoid information overload. A longer budget would likely widen the
# guided-vs-baseline gap — documented as a study limitation.
STUDY_TASK_DURATION_SECONDS = 600  # 10 minutes
STUDY_PARTIES = ["Venus", "Mars", "Saturn"]

# Subtopic catalog for claim grouping on the source pages. Slugs match the
# `subtopic` field in `data/study-fake-parties/positions/*.json`. The subtopic
# is metadata only — it is NOT embedded by scripts/embed_study_positions.py.
# Order here defines display order.
#
# Narrow by design (2 subtopics per topic, max 3 claims per party per subtopic)
# to keep the exploration tree scannable within the 10-minute task budget and
# leave room for a conversation-driven flow rather than exhaustive fact recall.
STUDY_SUBTOPICS: dict[str, list[tuple[str, str]]] = {
    "klimaschutz": [
        ("co2-preis", "CO2-Preis & Emissionshandel"),
        ("verkehr", "Verkehr & Mobilität"),
    ],
    "soziale-gerechtigkeit": [
        ("rente", "Rente & Altersvorsorge"),
        ("buergergeld", "Bürgergeld & Grundsicherung"),
    ],
}


class StudyConfig(BaseModel):
    """Configuration for a study."""

    context_id: str = Field(
        ...,
        description="The context ID for fake parties (e.g., 'study-fake-parties')",
    )
    topics: list[str] = Field(
        default=STUDY_TOPICS,
        description="List of topics for the study tasks (hardcoded)",
    )
    task_duration_seconds: int = Field(
        default=STUDY_TASK_DURATION_SECONDS,
        description="Duration in seconds for each task (hardcoded: 10 minutes)",
    )
    parties: list[str] = Field(
        default=STUDY_PARTIES,
        description="List of party names for the fake context (hardcoded)",
    )


class Study(BaseModel):
    """A study definition created by an admin."""

    id: str = Field(..., description="Unique study identifier")
    name: str = Field(..., description="Human-readable study name")
    status: StudyStatus = Field(
        default=StudyStatus.DRAFT,
        description="Current status of the study",
    )
    config: StudyConfig = Field(..., description="Study configuration")
    created_at: datetime = Field(..., description="When the study was created")
    updated_at: datetime = Field(..., description="When the study was last updated")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
