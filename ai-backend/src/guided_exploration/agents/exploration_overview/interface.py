# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Input model for the exploration-overview agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.position import Position


class OverviewAreaInput(BaseModel):
    """One top-level area passed to the agent."""

    name: str = Field(..., description="Display name of the area")
    description: str = Field(..., description="1-2 sentence description")
    party_ids: list[str] = Field(
        default_factory=list,
        description="Party IDs that have positions anywhere under this area",
    )


class ExplorationOverviewAgentInput(BaseModel):
    """Input for the exploration-overview agent."""

    query: str = Field(..., description="The user's original query")
    context_name: str = Field(..., description="Display name of the context")
    parties: dict[str, PartyInfo] = Field(
        ..., description="Map of party_id -> PartyInfo, in the order to render"
    )
    areas: list[OverviewAreaInput] = Field(
        ..., description="Top-level areas of the exploration tree"
    )
    positions_by_party: dict[str, list[Position]] = Field(
        default_factory=dict,
        description="All positions grouped by party_id, used to ground the per-party summaries",
    )
