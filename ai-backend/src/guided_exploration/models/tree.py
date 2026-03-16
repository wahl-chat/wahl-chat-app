# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for the topic tree structure in guided exploration."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Subtopic(BaseModel):
    """Leaf node - explorable content."""

    id: str = Field(..., description="Unique identifier, e.g., 'housing.rent-control'")
    name: str = Field(..., description="Display name, e.g., 'Rent Control'")
    description: str = Field(..., description="One sentence description")
    scope: str = Field(
        default="",
        description=(
            "Detailed scope description for knowledge extraction. Describes what "
            "aspects belong to this subtopic, what doesn't belong, and what kind "
            "of claims/positions/measures should be extracted."
        ),
    )
    parties: list[str] = Field(
        default_factory=list, description="Party IDs with positions on this subtopic"
    )
    status: Literal["pending", "explored"] = Field(
        default="pending", description="Exploration status"
    )


class Topic(BaseModel):
    """Branch node - contains subtopics. Can also be a leaf if subtopics is empty."""

    id: str = Field(..., description="Unique identifier, e.g., 'housing'")
    name: str = Field(..., description="Display name, e.g., 'Housing'")
    description: str = Field(..., description="Brief description of the topic")
    subtopics: list[Subtopic] = Field(
        default_factory=list, description="List of subtopics under this topic"
    )
    parties: list[str] = Field(
        default_factory=list,
        description="Party IDs with positions (used when topic is a leaf)",
    )
    status: Literal["pending", "partial", "explored"] = Field(
        default="pending", description="Aggregated exploration status"
    )


class TopicTree(BaseModel):
    """Full tree for an exploration."""

    exploration_id: str = Field(..., description="ID of the parent exploration")
    original_query: str = Field(
        ..., description="The user's original query that generated this tree"
    )
    topics: list[Topic] = Field(
        default_factory=list, description="Top-level topics in the tree"
    )
    created_at: datetime = Field(..., description="When the tree was created")
    updated_at: datetime = Field(..., description="When the tree was last updated")
