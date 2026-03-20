# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for followup router agent."""

from enum import Enum

from pydantic import BaseModel, Field


class LeafInfo(BaseModel):
    """Compact info about a leaf node for the router prompt."""

    id: str = Field(..., description="Leaf node ID")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Brief description")


class FollowupRoute(str, Enum):
    """Routing decision for a follow-up question."""

    ON_TOPIC_EXISTING = "on_topic_existing"
    ON_TOPIC_NEEDS_RAG = "on_topic_needs_rag"
    RELATED_TOPIC = "related_topic"
    OFF_TOPIC = "off_topic"


class FollowupRouterInput(BaseModel):
    """Input for followup routing."""

    message: str = Field(..., description="The user's follow-up question")
    leaf_id: str = Field(..., description="Current leaf node ID")
    leaf_name: str = Field(..., description="Display name of current leaf")
    leaf_description: str = Field(..., description="What this leaf covers")
    existing_claims_summary: str = Field(
        ..., description="Condensed summary of claims in this leaf"
    )
    other_leaves: list[LeafInfo] = Field(
        default_factory=list,
        description="All other leaf nodes in the tree",
    )
    context_name: str = Field(
        default="", description="Election context name"
    )


class FollowupRouterOutput(BaseModel):
    """Routing decision from the agent."""

    route: FollowupRoute = Field(..., description="The routing decision")
    target_node_id: str | None = Field(
        default=None,
        description="Target leaf ID when route is RELATED_TOPIC",
    )
    target_node_name: str | None = Field(
        default=None,
        description="Target leaf name when route is RELATED_TOPIC",
    )
