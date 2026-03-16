# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for analyzer agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.content import SubtopicContent
from src.guided_exploration.models.exploration import ResolvedKnowledge


class AnalyzerInput(BaseModel):
    """Input for analysis generation."""

    leaf_id: str = Field(..., description="ID of the leaf node to analyze")
    leaf_name: str = Field(..., description="Display name of the leaf")
    subtopic_content: SubtopicContent = Field(
        ..., description="The current subtopic content"
    )
    resolved_knowledge: ResolvedKnowledge = Field(
        ..., description="Pre-resolved knowledge for this subtopic"
    )
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Display name of the context")
    parties_info: dict[str, PartyInfo] = Field(
        ..., description="Party information keyed by party_id"
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Specific areas to focus the analysis on",
    )
