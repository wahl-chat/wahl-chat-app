# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for followup router agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.followup_router.interface import LeafInfo
from src.guided_exploration.models.position import Position


# =============================================================================
# LLM Output Schema
# =============================================================================


class FollowupRouterLLMOutput(BaseModel):
    """LLM output for routing decision."""

    route: str = Field(
        ...,
        description=(
            "Entscheidung: 'on_topic_existing' (beantwortbar mit vorhandenen Daten), "
            "'on_topic_needs_rag' (zum Thema passend aber mehr Details nötig), "
            "'related_topic' (passt besser zu einem anderen Thema), "
            "'off_topic' (nicht abgedeckt)"
        ),
    )
    rag_query: str | None = Field(
        default=None,
        description=(
            "Nur bei 'on_topic_needs_rag': Optimierte Suchbegriffe für die "
            "Dokumentensuche. Keine ganzen Sätze, nur prägnante Stichworte. "
            "Beispiel: 'Mindestlohn Erhöhung Arbeitnehmer Löhne'"
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
{existing_positions}

# Andere verfügbare Themen
{other_leaves}

# Routing-Regeln

Klassifiziere die Nutzerfrage in GENAU EINE Kategorie:

1. **on_topic_needs_rag** (**Standard für inhaltliche Fragen**): Die Frage passt zum \
aktuellen Thema '{leaf_name}' und verlangt Inhalte aus den Wahlprogrammen. Wähle das \
IMMER, sobald die Nutzerin etwas Konkretes, Detail-, Aspekt- oder Mechanik-bezogenes \
fragt — auch wenn die vorhandenen Positionen das Oberthema bereits grob abdecken. \
Beispiele: "Wie wird X finanziert?", "Was konkret fordert Y?", "Wie wirkt sich Z auf \
A aus?".

2. **on_topic_existing** (**Ausnahme, nur für Meta-/Trivialfragen**): Die Frage braucht \
KEINE neuen Inhalte aus den Wahlprogrammen. Nur erlaubt für:
   - Meta-Fragen zur Anzeige ("Welche Parteien sind dabei?", "Was heißt das Symbol?").
   - Reine Klarstellungen zu bereits sichtbarem Text ("Was genau meintest du mit X \
oben?").
   - Triviale Rückfragen ohne neuen inhaltlichen Anteil.

3. **related_topic**: Die Frage passt BESSER zu einem der anderen verfügbaren Themen. \
Gib die ID und den Namen des passenden Themas an (target_node_id, target_node_name).

4. **off_topic**: Die Frage hat nichts mit den verfügbaren Themen zu tun und kann \
auch nicht aus Wahlprogrammen beantwortet werden.

# Wichtig
- **Default ist 'on_topic_needs_rag'.** Im Zweifel immer RAG. Die vorhandenen \
Positionen sind eine grobe Übersicht — für jede konkrete Folgefrage lohnt sich \
zusätzliche Retrieval.
- 'on_topic_existing' NUR, wenn die Frage keine inhaltliche Parteiinformation \
verlangt (reine Meta-/Anzeige-Frage).
- 'related_topic' nur wenn ein anderes Thema DEUTLICH besser passt.

# RAG-Suchbegriffe (nur bei on_topic_needs_rag)
Wenn du 'on_topic_needs_rag' wählst, generiere optimierte Suchbegriffe im Feld \
'rag_query'. Regeln:
- NUR Stichworte, keine ganzen Sätze
- Keine Parteinamen oder Meta-Sprache ("Was sagen die Parteien zu...")
- Fachbegriffe und konkrete Themen verwenden
- Beispiel gut: "staatliche Förderung Wohneigentum Baukindergeld Zuschuss"
- Beispiel schlecht: "Wie sollen die staatlichen Zuschüsse konkret gestaltet werden?" """

USER_PROMPT = """Nutzerfrage: {message}

Klassifiziere diese Frage."""


def format_positions_for_routing(
    positions_by_party: dict[str, list[Position]],
    max_positions_per_party: int = 3,
) -> str:
    """Format positions as a compact summary for the routing prompt."""
    if not positions_by_party:
        return "Keine Informationen vorhanden."

    lines = []
    for party_id, positions in positions_by_party.items():
        position_texts = [p.content for p in positions[:max_positions_per_party]]
        if len(positions) > max_positions_per_party:
            position_texts.append(f"... (+{len(positions) - max_positions_per_party} weitere)")
        lines.append(f"{party_id.upper()}: {'; '.join(position_texts)}")

    return "\n".join(lines)


def format_other_leaves(leaves: list[LeafInfo]) -> str:
    """Format other leaves as compact list for the routing prompt."""
    if not leaves:
        return "Keine anderen Themen verfügbar."

    lines = []
    for leaf in leaves:
        lines.append(f"- {leaf.id}: {leaf.name} — {leaf.description}")

    return "\n".join(lines)
