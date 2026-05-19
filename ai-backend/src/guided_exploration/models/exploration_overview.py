# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for the exploration-overview message shown before the tree."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PartyStanceSummary(BaseModel):
    """One party's general stance and focus across the exploration areas."""

    party_id: str = Field(..., description="Party identifier (e.g., 'spd')")
    summary: str = Field(
        ...,
        description=(
            "1-3 sentences describing the party's general stance and where its "
            "focus lies across the exploration areas. No citations."
        ),
    )


class ExplorationOverview(BaseModel):
    """Structured overview shown as a chat message before the tree card."""

    intro_paragraph: str = Field(
        ...,
        description=(
            "Short paragraph (2-4 sentences) explaining why the tree was "
            "structured this way and naming each subtopic in one sentence "
            "each. No citations, no markdown headings."
        ),
    )
    party_summaries: list[PartyStanceSummary] = Field(
        default_factory=list,
        description="Per-party stance summary, ordered to match the tree's party order.",
    )
