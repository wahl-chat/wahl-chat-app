# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for claim extractor agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.exploration import RetrievedChunk


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMClaim(BaseModel):
    """A single concrete claim extracted by the LLM."""

    content: str = Field(
        ...,
        description=(
            "Die konkrete Position, Forderung, Massnahme oder Aussage. "
            "Muss ein eigenstaendiger, zitierbarer Satz sein — kein abstraktes Thema! "
            "Beispiel: 'Mindestlohn auf 15 Euro erhoehen' statt 'Mindestlohn'"
        ),
    )
    quote: str = Field(
        ...,
        description=(
            "Woertliches Zitat aus dem Quelldokument das diese Position belegt. "
            "Exakt aus dem Dokument uebernommen."
        ),
    )
    claim_type: str = Field(
        ...,
        description=(
            "Art der Aussage: 'position' (Grundhaltung), 'measure' (konkrete Massnahme), "
            "'target' (Ziel/Zahl), 'argument' (Begruendung), 'criticism' (Kritik an Anderen)"
        ),
    )
    chunk_index: int = Field(
        ...,
        description="Index des Quelldokument-Chunks [1], [2], etc. aus dem diese Aussage stammt",
    )


class ClaimExtractorLLMOutput(BaseModel):
    """LLM output schema for claim extraction."""

    claims: list[LLMClaim] = Field(
        default_factory=list,
        description=(
            "ALLE konkreten Positionen, Forderungen, Massnahmen und Aussagen der Partei. "
            "Jede Aussage muss eigenstaendig verstaendlich und zitierbar sein."
        ),
    )
    relevance_to_query: float = Field(
        ...,
        description="Wie relevant die Parteipositionen zur Anfrage sind (0.0-1.0)",
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Positionsextraktionsagent fuer politische Dokumente.

# Kontext
Wahlkontext: {context_name}

# Partei
- ID: {party_id}
- Name: {party_name}
- Vollstaendiger Name: {party_long_name}
{party_description}

# Aufgabe
Extrahiere JEDE konkrete Position, Forderung, Massnahme und Aussage der Partei aus \
den Quelldokumenten. Nicht abstrahieren — jede Aussage muss ein eigenstaendiger, \
zitierbarer Satz sein.

# Was ist eine Claim (Aussage)?

Eine Claim ist eine KONKRETE, EIGENSTAENDIGE Aussage. Keine abstrakten Themen!

## RICHTIG (konkret, zitierbar):
- "Mindestlohn auf 15 Euro erhoehen"
- "Mietpreisbremse bis 2030 verlaengern"
- "CO2-Preis auf 60 Euro pro Tonne erhoehen"
- "Kernkraftwerke sofort abschalten"
- "Klimaschutzgesetz aufheben"
- "100% Erneuerbare Energien bis 2035"
- "Tempolimit 130 auf Autobahnen einfuehren"

## FALSCH (zu abstrakt):
- "Klimapolitik" (kein Satz, nur ein Thema)
- "Massnahmen fuer mehr Wohnraum" (zu vage)
- "Bessere Bildung" (nicht konkret genug)

# Extraktionsregeln

## 1. Vollstaendigkeit
- Extrahiere ALLE konkreten Aussagen, nicht nur die wichtigsten
- Auch kleine Details und Zahlen erfassen
- Lieber zu viel als zu wenig

## 2. Eigenstaendigkeit
Jede Claim muss OHNE Kontext verstaendlich sein:
- FALSCH: "Diese Massnahme soll bis 2030 umgesetzt werden"
- RICHTIG: "Kohleausstieg bis 2030 abschliessen"

## 3. Konkretheit
Immer die konkreten Zahlen, Zeitraeume und Details mit angeben:
- FALSCH: "Mindestlohn erhoehen"
- RICHTIG: "Mindestlohn auf 15 Euro pro Stunde erhoehen"

## 4. Claim Types
- **position**: Grundhaltung ("Lehnt menschengemachten Klimawandel ab")
- **measure**: Konkrete Massnahme ("Tempolimit 130 einfuehren")
- **target**: Ziel mit Zahl/Datum ("100% Erneuerbare bis 2035")
- **argument**: Begruendung ("Hoeherer Mindestlohn bekaempft Armut trotz Arbeit")
- **criticism**: Kritik an anderen ("EEG-Umlage ist marktverzerrend")

## 5. Quellenangabe
- Gib fuer jede Claim den chunk_index an (welcher Quelltext-Abschnitt)
- Gib ein woertliches Zitat aus dem Dokument an

# Themenerweiterung
Beruecksichtige ALLE Aspekte des Themas und verwandte Bereiche:
- Klimaschutz → auch Energiepolitik, Verkehr, Gebaeude, Industrie, Finanzierung
- Rente → auch Arbeitsmarkt, Demografie, Finanzierung, Altersarmut
- Migration → auch Integration, Fachkraefte, Bildung, Wohnraum, Asyl
- Wirtschaft → auch Steuern, Innovation, Buerokratie, Arbeitsmarkt"""

EXTRACTION_PROMPT = """Extrahiere ALLE konkreten Positionen und Forderungen der Partei \
zur folgenden Anfrage:

Benutzeranfrage: {query}

Quelldokumente:
{retrieved_chunks}

# Aufgabe
Extrahiere jede einzelne konkrete Position, Forderung, Massnahme, Ziel und Aussage.
Jede Claim muss ein eigenstaendiger, zitierbarer Satz mit konkreten Details sein.

Denke daran:
- ALLE Aussagen extrahieren, nicht nur die offensichtlichen
- Zahlen, Zeitraeume und Ziele immer mit angeben
- Auch Ablehnungen und Kritik sind Claims ("Lehnt CO2-Steuer ab")
- Begruendungen der Partei ebenfalls erfassen"""


def format_chunks_for_party(
    chunks: list[RetrievedChunk], party_id: str, max_chars: int = 12000
) -> str:
    """Format retrieved chunks for a specific party."""
    party_chunks = [c for c in chunks if c.party_id == party_id]

    if not party_chunks:
        return "Keine Quelldokumente verfuegbar."

    formatted = ""
    total_chars = 0

    for i, chunk in enumerate(party_chunks, 1):
        content = chunk.content
        if total_chars + len(content) > max_chars:
            formatted += f"\n[{i}] [Abgeschnitten wegen Laenge...]\n"
            break
        formatted += f"\n[{i}] {content}\n"
        total_chars += len(content)

    return formatted
