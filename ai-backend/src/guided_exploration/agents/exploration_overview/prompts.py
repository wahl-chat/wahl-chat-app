# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompts for the exploration-overview agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.exploration_overview.interface import (
    OverviewAreaInput,
)
from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.position import Position


class PartyStanceLLMOutput(BaseModel):
    """One party stance entry in the LLM output."""

    party_id: str = Field(..., description="Party-ID exakt wie in der Eingabe.")
    summary: str = Field(
        ...,
        description=(
            "1–2 kurze Sätze auf Deutsch, passiv/unpersönlich formuliert, "
            "die die generelle Stoßrichtung der Partei beschreiben. Keine "
            "konkreten Forderungen, Zahlen, Beträge oder Policy-Namen. "
            "Keine Anrede der Lesenden, keine du-Form, keine wir-Form. "
            "Keine Zitate, keine Quellenangaben, keine Marker wie [1]."
        ),
    )


class ExplorationOverviewLLMOutput(BaseModel):
    """LLM output schema for the exploration overview."""

    intro_paragraph: str = Field(
        ...,
        description=(
            "Kurze Einleitung auf Deutsch (Markdown erlaubt), passiv/"
            "unpersönlich formuliert, die jeden Themenbereich knapp "
            "vorstellt. Der Name jedes Themenbereichs wird in **fett** "
            "(Markdown) hervorgehoben. Kurze Sätze, je Bereich höchstens "
            "ein Satz. Keine Anrede der Lesenden, keine du-Form, keine "
            "wir-Form, keine Überschriften, keine Zitate."
        ),
    )
    party_summaries: list[PartyStanceLLMOutput] = Field(
        ...,
        description=(
            "Pro Partei genau ein Eintrag, in der vorgegebenen Reihenfolge. "
            "Genau die Parteien aus der Eingabe, keine zusätzlichen."
        ),
    )


SYSTEM_PROMPT = """Du fasst eine Themen-Erkundung für Wahlprogramme zusammen.

# Kontext
Wahlkontext: {context_name}

{party_context}

# Aufgabe
Du erhältst eine Nutzerfrage, eine Liste von Themenbereichen (mit \
Beschreibungen) und die zugehörigen Parteipositionen.

Erzeuge zwei Dinge:

1. **intro_paragraph** — eine kurze Einleitung in Markdown, die jeden \
Themenbereich knapp einführt. Der **Name jedes Themenbereichs** steht in \
**fett** (Markdown-`**…**`). Pro Bereich höchstens ein Satz, sehr kurz. \
Stil-Beispiel: "Im Folgenden geht es um drei Aspekte. Bei **<Bereich A>** \
steht <kurze sachliche Charakterisierung> im Vordergrund. **<Bereich B>** \
dreht sich um …. Im Bereich **<Bereich C>** geht es um …."

2. **party_summaries** — pro Partei 1–2 sehr kurze Sätze, die die \
übergeordnete Stoßrichtung der Partei zur Nutzerfrage benennen. Auf hoher \
Flughöhe, ohne konkrete Forderungen, Zahlen, Beträge, Policy-Namen oder \
spezifische Maßnahmen — solche Details gehören in die einzelnen \
Themenkarten, nicht hierhin. Stattdessen das übergeordnete Muster \
benennen, z.B. "Der Fokus liegt auf staatlicher Absicherung und \
Umverteilung." oder "Der Schwerpunkt liegt auf Eigenverantwortung und \
Aktivierung." oder "Die Stoßrichtung ist restriktiv beim Zugang zu \
Sozialleistungen."

# Sprachregeln (sehr wichtig)
- Passive oder unpersönliche Formulierungen, immer *über das Thema* — nie \
  über die Lesenden und nie über die Partei als handelnde Person, die \
  angesprochen wird.
  - Korrekt:   "Der Fokus liegt auf …", "Im Vordergrund steht …", \
"Die Partei setzt einen Schwerpunkt auf …", "Bei <Bereich> geht es um …".
  - Falsch:    "Du setzt …", "Du erfährst …", "Wir zeigen …", "Du \
verbindest …", "Du legst den Schwerpunkt auf …".
- Keine Anrede der Lesenden. Keine du-Form, keine wir-Form, keine \
  Imperative an die Lesenden.
- Kurze Sätze, ein Hauptgedanke pro Satz. Keine Schachtelsätze mit \
  Doppelpunkt-und-Aufzählung. Keine "sowie"-Listen.

# Inhaltliche Regeln
- Halte dich an die vorgegebene Parteienliste und -reihenfolge.
- In **party_summaries**: keine konkreten Zahlen, Beträge, Policy-Namen, \
  Paragraphen oder einzelnen Maßnahmen. Nur die übergeordnete Richtung. \
  Wenn eine Partei kaum vertreten ist, knapp festhalten ("legt zu diesem \
  Thema wenig Schwerpunkt") statt zu spekulieren.
- Erfinde keine Positionen, die in den Eingabe-Positionen nicht stehen.
- Keine pauschalen Werturteile ("am besten", "am sinnvollsten").
- Schreibe knapp. Lieber zu kurz als zu lang."""


USER_PROMPT = """# Nutzerfrage
{query}

# Themenbereiche
{areas_block}

# Parteipositionen pro Partei
{positions_block}

# Erwartete Reihenfolge der Parteien in party_summaries
{party_order}

Erzeuge intro_paragraph und party_summaries gemäß den Regeln."""


def format_areas_block(
    areas: list[OverviewAreaInput],
    parties: dict[str, PartyInfo],
) -> str:
    """Format the areas for the user prompt."""
    if not areas:
        return "Keine Bereiche."
    lines: list[str] = []
    for area in areas:
        party_names = [parties[pid].name for pid in area.party_ids if pid in parties]
        suffix = f" (Parteien: {', '.join(party_names)})" if party_names else ""
        lines.append(f"- {area.name}: {area.description}{suffix}")
    return "\n".join(lines)


def format_positions_block(
    positions_by_party: dict[str, list[Position]],
    parties: dict[str, PartyInfo],
) -> str:
    """Format party positions grouped per party for the user prompt."""
    if not positions_by_party:
        return "Keine Positionen verfügbar."
    chunks: list[str] = []
    for party_id, party_info in parties.items():
        party_positions = positions_by_party.get(party_id, [])
        if not party_positions:
            chunks.append(f"## {party_info.name}\nKeine Positionen extrahiert.")
            continue
        bullets = [f"- ({p.position_type}) {p.content}" for p in party_positions]
        chunks.append(f"## {party_info.name}\n" + "\n".join(bullets))
    return "\n\n".join(chunks)


def format_party_order(parties: dict[str, PartyInfo]) -> str:
    """Format the party order for the user prompt."""
    return ", ".join(f"{pid} ({info.name})" for pid, info in parties.items())
