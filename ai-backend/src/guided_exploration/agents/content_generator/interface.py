# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for content generator agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.claim import Claim
from src.guided_exploration.models.content import Citation


class ContentGeneratorInput(BaseModel):
    """Input for content generation from claims."""

    subtopic_id: str = Field(..., description="ID of the leaf node")
    subtopic_name: str = Field(..., description="Display name")
    path: list[str] = Field(
        ..., description="Path in tree, e.g., ['energie', 'erneuerbare']"
    )
    leaf_claims: dict[str, list[Claim]] = Field(
        ..., description="Claims grouped by party_id"
    )
    leaf_citations: list[Citation] = Field(
        default_factory=list,
        description="All citations for this leaf's claims",
    )
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Human-readable context name")
    parties_info: dict[str, PartyInfo] = Field(
        ..., description="Map of party_id -> PartyInfo for all parties"
    )
    parties: list[str] = Field(
        default_factory=list,
        description="Optional party filter - if empty, use all parties",
    )
