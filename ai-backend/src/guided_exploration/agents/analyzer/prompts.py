# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for analyzer agent."""

from pydantic import BaseModel, Field


class AnalysisLLMOutput(BaseModel):
    """LLM output schema for analysis generation."""

    summary: str = Field(
        ...,
        description="Kritische Einordnung in 2-3 Saetzen. Bewerte die Positionen auf Realismus.",
    )
    context: str = Field(
        ...,
        description="Relevanter Hintergrund und aktuelle Lage in 2-3 Saetzen",
    )
    feasibility: list[str] = Field(
        ...,
        description="3-4 Stichpunkte zur praktischen Umsetzbarkeit (rechtlich, finanziell, politisch)",
    )
    considerations: list[str] = Field(
        ...,
        description="3-4 Stichpunkte zu Risiken, Nebenwirkungen und langfristigen Auswirkungen",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Relevante Quellen oder Institute fuer weitere Information",
    )


SYSTEM_PROMPT = """Du bist ein kritischer Politikanalyst.

# Aufgabe
Erstelle realistische, fundierte Einordnungen politischer Positionen.

# Analyseprinzipien

## Kritisch aber fair
- Hinterfrage politische Versprechen auf ihre Machbarkeit
- Pruefe finanzielle und rechtliche Rahmenbedingungen
- Beruecksichtige EU-Recht, Grundgesetz und bestehende Gesetze

## Realismus bevorzugen
- Bei mehreren Positionen die realistischeren hervorheben
- Wunschdenken von umsetzbaren Massnahmen unterscheiden
- Nenne konkrete Zahlen und Fakten zur Untermauerung

## Konkrete Analyse
- Nenne spezifische Huerden (Kosten, Gesetze, Umsetzung, politische Mehrheiten)
- Beruecksichtige Haushaltslage und Finanzierbarkeit
- Analysiere praktische Umsetzungshuerden

## Ausgewogenheit
- Staerken UND Schwaechen jeder Position benennen
- Keine Partei bevorzugen oder benachteiligen
- Vermeide wertende Adjektive

# Leitlinien

## Neutralitaet
- KEINE Wahlempfehlungen geben
- Sachlich und faktenbasiert bleiben
- Formuliere kritische Punkte neutral

## Transparenz
- Kennzeichne Unsicherheiten klar
- Unterscheide zwischen Fakten und Einschaetzungen
- Nenne Quellen fuer weitere Information

## Antwortstil
- Schreibe auf Deutsch
- Kurze, praegnante Saetze
- Erklaere Fachbegriffe kurz"""

ANALYSIS_PROMPT = """Erstelle eine kritische Analyse:

**Thema:** {leaf_name} ({context_name})

## Parteipositionen:
{party_positions}
{focus_instruction}

## Deine Aufgabe:

1. **summary** (2-3 Saetze): Kritische Einordnung der Positionen. Welche Ansaetze sind realistischer? Wo gibt es Widersprueche oder unrealistische Versprechen?

2. **context** (2-3 Saetze): Aktueller Stand, relevante Rahmenbedingungen (EU-Recht, Haushaltslage, bestehende Gesetze)

3. **feasibility** (3-4 Punkte): Konkrete Huerden und Chancen der Umsetzung:
   - Rechtliche Machbarkeit
   - Finanzierbarkeit
   - Politische Durchsetzbarkeit
   - Praktische Umsetzung

4. **considerations** (3-4 Punkte): Was sollte man bedenken?
   - Moegliche Nebenwirkungen
   - Langfristige Auswirkungen
   - Wer profitiert, wer verliert?

Sei kritisch aber sachlich. Bevorzuge realistische Perspektiven gegenueber Wunschdenken."""


def format_focus_areas(focus_areas: list[str]) -> str:
    """Format focus areas instruction."""
    if not focus_areas:
        return ""

    return "\n## Fokus der Analyse:\n" + "\n".join(f"- {area}" for area in focus_areas)


def format_party_positions_for_analysis(
    positions: dict, parties_info: dict | None = None
) -> str:
    """Format party positions (ExtractedPosition) for analysis prompt."""
    if not positions:
        return "Keine Parteipositionen verfuegbar."

    formatted = ""
    for party_id, position in positions.items():
        # Get party name from info if available
        if parties_info and party_id in parties_info:
            party_name = parties_info[party_id].name
        else:
            party_name = party_id.upper()

        formatted += f"\n**{party_name}:**"
        if position.summary:
            formatted += f" {position.summary}\n"
        else:
            formatted += "\n"

        # Add positions as key points
        if position.positions:
            for pos_item in position.positions[:3]:  # Limit to 3 positions
                formatted += f"  - {pos_item.position}"
                if pos_item.citation_id:
                    formatted += f" [{pos_item.citation_id}]"
                formatted += "\n"

    return formatted
