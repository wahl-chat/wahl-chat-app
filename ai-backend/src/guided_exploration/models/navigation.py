# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for navigation state in guided exploration."""

from enum import Enum

from pydantic import BaseModel, Field


class BreadcrumbLevel(str, Enum):
    """Level in the navigation hierarchy."""

    ROOT = "root"
    TOPIC = "topic"
    SUBTOPIC = "subtopic"


class BreadcrumbItem(BaseModel):
    """Item in navigation breadcrumb."""

    id: str = Field(..., description="Unique identifier for the breadcrumb item")
    name: str = Field(..., description="Display name for the breadcrumb")
    level: BreadcrumbLevel = Field(..., description="Level in the navigation hierarchy")


class NavigationState(BaseModel):
    """Current position in the exploration tree."""

    exploration_id: str = Field(..., description="ID of the current exploration")
    current_path: list[str] = Field(
        default_factory=list,
        description="Current path in tree. [] = root, ['housing'] = topic, etc.",
    )
    breadcrumb: list[BreadcrumbItem] = Field(
        default_factory=list,
        description="Breadcrumb trail for navigation display",
    )


class SiblingNavigation(BaseModel):
    """Previous/next sibling info for leaf navigation."""

    previous: BreadcrumbItem | None = Field(
        default=None, description="Previous sibling in the current level"
    )
    next: BreadcrumbItem | None = Field(
        default=None, description="Next sibling in the current level"
    )
