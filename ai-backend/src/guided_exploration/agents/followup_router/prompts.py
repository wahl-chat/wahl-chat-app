# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for followup router agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.followup_router.interface import LeafInfo
from src.guided_exploration.models.claim import Claim


# =============================================================================
# LLM Output Schema
# =============================================================================


class FollowupRouterLLMOutput(BaseModel):
    """LLM output for routing decision."""

    route: str = Field(
        ...,
        description=(
            "Entscheidung: 'on_topic_existing' (beantwortbar mit vorhandenen Daten), "
            "'on_topic_needs_rag' (zum Thema passend aber mehr Details noetig), "
            "'related_topic' (passt besser zu einem anderen Thema), "
            "'off_topic' (nicht abgedeckt)"
        ),
    )
    target_node_id: str | None = Field(
        default=None,
        description="Nur bei 'related_topic': ID des passenden Themas",
    )
    target_node_name: str | None = Field(
        default=None,
        description="Nur bei 'related_topic': Name des passenden Themas",
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Routing-Agent. Deine Aufgabe ist es, Nutzerfragen \
schnell zu klassifizieren.

# Aktuelles Thema
Name: {leaf_name}
Beschreibung: {leaf_description}

# Vorhandene Informationen zu diesem Thema
{existing_claims}

# Andere verfuegbare Themen
{other_leaves}

# Routing-Regeln

Klassifiziere die Nutzerfrage in GENAU EINE Kategorie:

1. **on_topic_existing**: Die Frage kann mit den VORHANDENEN Informationen beantwortet \
werden. Die Antwort steht bereits in den oben aufgelisteten Positionen.

2. **on_topic_needs_rag**: Die Frage passt zum aktuellen Thema '{leaf_name}', aber \
die vorhandenen Informationen reichen nicht aus. Es koennten aber weitere Details in \
den Wahlprogrammen stehen. Beispiel: Eine Detailfrage zu einem Aspekt der nur \
oberflaeechlich in den Claims vorkommt.

3. **related_topic**: Die Frage passt BESSER zu einem der anderen verfuegbaren Themen. \
Gib die ID und den Namen des passenden Themas an (target_node_id, target_node_name).

4. **off_topic**: Die Frage hat nichts mit den verfuegbaren Themen zu tun und kann \
auch nicht aus Wahlprogrammen beantwortet werden.

# Wichtig
- Bevorzuge 'on_topic_existing' wenn die Frage auch nur teilweise beantwortbar ist
- Nutze 'on_topic_needs_rag' nur wenn die Frage klar zum Thema passt aber mehr \
Details braucht
- Nutze 'related_topic' nur wenn ein anderes Thema DEUTLICH besser passt"""

USER_PROMPT = """Nutzerfrage: {message}

Klassifiziere diese Frage."""


def format_claims_for_routing(
    claims_by_party: dict[str, list[Claim]],
    max_claims_per_party: int = 3,
) -> str:
    """Format claims as a compact summary for the routing prompt."""
    if not claims_by_party:
        return "Keine Informationen vorhanden."

    lines = []
    for party_id, claims in claims_by_party.items():
        claim_texts = [c.content for c in claims[:max_claims_per_party]]
        if len(claims) > max_claims_per_party:
            claim_texts.append(f"... (+{len(claims) - max_claims_per_party} weitere)")
        lines.append(f"{party_id.upper()}: {'; '.join(claim_texts)}")

    return "\n".join(lines)


def format_other_leaves(leaves: list[LeafInfo]) -> str:
    """Format other leaves as compact list for the routing prompt."""
    if not leaves:
        return "Keine anderen Themen verfuegbar."

    lines = []
    for leaf in leaves:
        lines.append(f"- {leaf.id}: {leaf.name} — {leaf.description}")

    return "\n".join(lines)
