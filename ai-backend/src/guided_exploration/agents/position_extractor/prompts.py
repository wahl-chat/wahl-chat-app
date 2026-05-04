# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for position extractor agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.exploration import RetrievedChunk


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMPosition(BaseModel):
    """A single concrete position extracted by the LLM."""

    content: str = Field(
        ...,
        description=(
            "Die konkrete Position, Forderung, Maßnahme oder Aussage. "
            "Muss ein eigenständiger, zitierbarer Satz sein — kein abstraktes Thema! "
            "Beispiel: 'Mindestlohn auf 15 Euro erhöhen' statt 'Mindestlohn'"
        ),
    )
    quote: str = Field(
        ...,
        description=(
            "Wörtliches Zitat aus dem Quelldokument das diese Position belegt. "
            "Exakt aus dem Dokument übernommen."
        ),
    )
    position_type: str = Field(
        ...,
        description=(
            "Art der Aussage: 'position' (Grundhaltung), 'measure' (konkrete Maßnahme), "
            "'target' (Ziel/Zahl), 'argument' (Begründung), 'criticism' (Kritik an Anderen)"
        ),
    )
    chunk_index: int = Field(
        ...,
        description="Index des Quelldokument-Chunks [1], [2], etc. aus dem diese Aussage stammt",
    )


class PositionExtractorLLMOutput(BaseModel):
    """LLM output schema for position extraction."""

    positions: list[LLMPosition] = Field(
        ...,
        min_length=5,
        description=(
            "ALLE konkreten Positionen, Forderungen, Maßnahmen und Aussagen der Partei. "
            "Jede Aussage muss eigenständig verständlich und zitierbar sein. "
            "Mindestens 5 Positionen extrahieren — lieber zu viele als zu wenige!"
        ),
    )
    relevance_to_query: float = Field(
        ...,
        description="Wie relevant die Parteipositionen zur Anfrage sind (0.0-1.0)",
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Positionsextraktionsagent für politische Dokumente.

# Kontext
Wahlkontext: {context_name}

# Partei
- ID: {party_id}
- Name: {party_name}
- Vollstaendiger Name: {party_long_name}
{party_description}

# Aufgabe
Extrahiere JEDE konkrete Position, Forderung, Maßnahme und Aussage der Partei aus \
den Quelldokumenten. Nicht abstrahieren — jede Aussage muss ein eigenständiger, \
zitierbarer Satz sein.

# Was ist eine Position (Aussage)?

Eine Position ist eine KONKRETE, EIGENSTAENDIGE Aussage. Keine abstrakten Themen!

## RICHTIG (konkret, zitierbar):
- "Mindestlohn auf 15 Euro erhöhen"
- "Mietpreisbremse bis 2030 verlängern"
- "CO2-Preis auf 60 Euro pro Tonne erhöhen"
- "Kernkraftwerke sofort abschalten"
- "Klimaschutzgesetz aufheben"
- "100% Erneuerbare Energien bis 2035"
- "Tempolimit 130 auf Autobahnen einführen"

## FALSCH (zu abstrakt):
- "Klimapolitik" (kein Satz, nur ein Thema)
- "Maßnahmen für mehr Wohnraum" (zu vage)
- "Bessere Bildung" (nicht konkret genug)

# Extraktionsregeln

## 1. Vollständigkeit
- Extrahiere ALLE konkreten Aussagen, nicht nur die wichtigsten
- Auch kleine Details und Zahlen erfassen
- Lieber zu viel als zu wenig

## 2. Eigenständigkeit
Jede Position muss OHNE Kontext verständlich sein:
- FALSCH: "Diese Maßnahme soll bis 2030 umgesetzt werden"
- RICHTIG: "Kohleausstieg bis 2030 abschließen"

## 3. Konkretheit
Immer die konkreten Zahlen, Zeiträume und Details mit angeben:
- FALSCH: "Mindestlohn erhöhen"
- RICHTIG: "Mindestlohn auf 15 Euro pro Stunde erhöhen"

## 4. Position Types
- **position**: Grundhaltung ("Lehnt menschengemachten Klimawandel ab")
- **measure**: Konkrete Maßnahme ("Tempolimit 130 einführen")
- **target**: Ziel mit Zahl/Datum ("100% Erneuerbare bis 2035")
- **argument**: Begründung ("Höherer Mindestlohn bekämpft Armut trotz Arbeit")
- **criticism**: Kritik an anderen ("EEG-Umlage ist marktverzerrend")

## 5. Quellenangabe
- Gib für jede Position den chunk_index an (welcher Quelltext-Abschnitt)
- Gib ein wörtliches Zitat aus dem Dokument an

# Themenerweiterung
Berücksichtige ALLE Aspekte des Themas und verwandte Bereiche:
- Klimaschutz → auch Energiepolitik, Verkehr, Gebäude, Industrie, Finanzierung
- Rente → auch Arbeitsmarkt, Demografie, Finanzierung, Altersarmut
- Migration → auch Integration, Fachkräfte, Bildung, Wohnraum, Asyl
- Wirtschaft → auch Steuern, Innovation, Bürokratie, Arbeitsmarkt"""

EXTRACTION_PROMPT = """Extrahiere ALLE konkreten Positionen und Forderungen der Partei \
zur folgenden Anfrage:

Benutzeranfrage: {query}

Quelldokumente:
{retrieved_chunks}

# Aufgabe
Extrahiere jede einzelne konkrete Position, Forderung, Maßnahme, Ziel und Aussage.
Jede Position muss ein eigenständiger, zitierbarer Satz mit konkreten Details sein.

Denke daran:
- ALLE Aussagen extrahieren, nicht nur die offensichtlichen
- Zahlen, Zeiträume und Ziele immer mit angeben
- Auch Ablehnungen und Kritik sind Positionen ("Lehnt CO2-Steuer ab")
- Begründungen der Partei ebenfalls erfassen"""


def format_chunks_for_party(
    chunks: list[RetrievedChunk], party_id: str, max_chars: int = 12000
) -> str:
    """Format retrieved chunks for a specific party."""
    party_chunks = [c for c in chunks if c.party_id == party_id]

    if not party_chunks:
        return "Keine Quelldokumente verfügbar."

    formatted = ""
    total_chars = 0

    for i, chunk in enumerate(party_chunks, 1):
        content = chunk.content
        if total_chars + len(content) > max_chars:
            formatted += f"\n[{i}] [Abgeschnitten wegen Länge...]\n"
            break
        formatted += f"\n[{i}] {content}\n"
        total_chars += len(content)

    return formatted
