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
STUDY_TASK_DURATION_SECONDS = 600  # 10 minutes
STUDY_PARTIES = ["Merkur", "Venus", "Mars", "Jupiter", "Saturn"]


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
