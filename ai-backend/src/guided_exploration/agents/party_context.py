# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared utilities for party context formatting in agent prompts."""

from pydantic import BaseModel, Field

from src.models.context import ContextParty


class PartyInfo(BaseModel):
    """Simplified party information for agent prompts."""

    party_id: str = Field(..., description="Party identifier (e.g., 'spd')")
    name: str = Field(..., description="Short name (e.g., 'SPD')")
    long_name: str = Field(..., description="Full name")
    description: str | None = Field(None, description="Brief political description")


def context_party_to_info(party: ContextParty) -> PartyInfo:
    """Convert ContextParty to simplified PartyInfo."""
    return PartyInfo(
        party_id=party.party_id,
        name=party.name,
        long_name=party.long_name,
        description=party.description,
    )


def parties_to_info_map(parties: list[ContextParty]) -> dict[str, PartyInfo]:
    """Convert list of ContextParty to a map of party_id -> PartyInfo."""
    return {p.party_id: context_party_to_info(p) for p in parties}


def format_party_context_for_prompt(
    parties: dict[str, PartyInfo],
    context_name: str | None = None,
) -> str:
    """
    Format party context information for LLM prompts.

    Args:
        parties: Map of party_id -> PartyInfo
        context_name: Optional context name (e.g., "Bundestagswahl 2025")

    Returns:
        Formatted string for inclusion in prompts.
    """
    lines = []

    if context_name:
        lines.append(f"Kontext: {context_name}")
        lines.append("")

    lines.append("Beteiligte Parteien:")
    for party_id, info in parties.items():
        desc_part = f" - {info.description}" if info.description else ""
        lines.append(f"- {party_id}: {info.name} ({info.long_name}){desc_part}")

    return "\n".join(lines)
