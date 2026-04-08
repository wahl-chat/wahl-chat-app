# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for hierarchy builder agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.position import Position


class HierarchyBuilderInput(BaseModel):
    """Input for hierarchy construction from positions."""

    query: str = Field(..., description="The user's original query")
    context_name: str = Field(..., description="Display name of the context")
    parties: dict[str, PartyInfo] = Field(
        ..., description="Map of party_id -> PartyInfo"
    )
    all_positions: list[Position] = Field(
        ..., description="All positions from all parties, combined"
    )


class HierarchyBuilderOutput(BaseModel):
    """Output: a hierarchical tree structure organizing the positions."""

    # The LLM output is converted into ExplorationNode/ExplorationTree
    # by the implementation. This output carries the intermediate result.
    tree_json: dict = Field(
        ..., description="Serialized ExplorationNode tree structure"
    )
    position_assignment: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapping of leaf_node_id -> list of position_ids assigned to it",
    )
