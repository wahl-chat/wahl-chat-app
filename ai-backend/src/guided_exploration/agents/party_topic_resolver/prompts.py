# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for party topic resolver agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.exploration import RetrievedChunk


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMSubtopic(BaseModel):
    """A subtopic/talking point extracted by the LLM."""

    id: str = Field(
        ..., description="Eindeutige ID fuer das Unterthema, z.B. 'mietregulierung'"
    )
    name: str = Field(
        ..., description="Name des Talking Points (z.B. 'Mindestlohn erhoehen')"
    )
    description: str = Field(..., description="Kurze Beschreibung (1-2 Saetze)")
    rationale: str = Field(
        ...,
        description=(
            "Erklaerung was zu diesem Unterthema gehoert und wie es abgegrenzt wird. "
            "Beschreibe: (1) Welche Aspekte fallen darunter? (2) Was gehoert NICHT dazu? "
            "(3) Welche konkreten Forderungen/Massnahmen der Partei gehoeren hierher? "
            "(Ein Absatz, 3-5 Saetze)"
        ),
    )
    has_content: bool = Field(
        default=True, description="True wenn die Partei hierzu Inhalte hat"
    )


class LLMTopic(BaseModel):
    """A topic extracted by the LLM."""

    id: str = Field(..., description="Eindeutige ID fuer das Thema, z.B. 'wohnen'")
    name: str = Field(
        ...,
        description="Oberbegriff fuer das Thema (z.B. 'Wohnungspolitik')",
    )
    description: str = Field(..., description="Kurze Beschreibung des Themas")
    subtopics: list[LLMSubtopic] = Field(
        default_factory=list,
        description="Unterthemen/Talking Points zu diesem Thema (4-8)",
    )
    importance_score: float = Field(
        ..., description="Wie stark die Partei dieses Thema betont (0.0-1.0)"
    )


class PartyTopicsLLMOutput(BaseModel):
    """LLM output schema for party topic resolution."""

    topics: list[LLMTopic] = Field(
        default_factory=list,
        description="Extrahierte Themen mit vielen Talking Points (5-8 Themen, ~25 Talking Points gesamt)",
    )
    relevance_to_query: float = Field(
        ..., description="Wie gut die Parteithemen zur Anfrage passen (0.0-1.0)"
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Themenextraktionsagent fuer politische Inhalte.

# Kontext
Wahlkontext: {context_name}

# Partei
- ID: {party_id}
- Name: {party_name}
- Vollstaendiger Name: {party_long_name}
{party_description}

# Aufgabe
Extrahiere ALLE relevanten Themen und Talking Points aus den Parteimaterialien.
Ziel: Moeglichst umfassende Extraktion (~25 Talking Points), damit spaeter kombiniert werden kann.

# Kernziel
Extrahiere ALLES was die Partei zu einem Thema sagt - ohne zu filtern!
Die Vergleichbarkeit wird spaeter vom Topic Combiner hergestellt.

# Extraktionsregeln

## 1. Umfassend extrahieren
- Extrahiere ALLE Positionen, Forderungen und Massnahmen der Partei
- Auch parteispezifische Themen sind relevant
- Lieber zu viel als zu wenig extrahieren

## 2. Themenerweiterung - WICHTIG!
Beruecksichtige bei jedem Thema auch VERWANDTE und BENACHBARTE Aspekte:
- **Klimaschutz** → Finanzierung, Generationengerechtigkeit, Wirtschaftsfolgen, Technologie, Energiewende
- **Rente** → Generationenvertrag, Arbeitsmarkt, Demografie, Finanzierung, Altersarmut
- **Migration** → Arbeitsmarkt, Fachkraefte, Integration, Bildung, Wohnraum, Asyl
- **Bildung** → Chancengleichheit, Digitalisierung, Arbeitsmarkt, Foederalismus, Ausbildung
- **Wirtschaft** → Arbeitsplaetze, Steuern, Innovation, Standortwettbewerb, Buerokratie

## 3. Neutrale Formulierung
- Keine wertenden Adjektive
- Aber parteispezifische Begriffe sind OK (werden spaeter vereinheitlicht)

## 4. IDs
Kurze, beschreibende IDs (z.B. 'mieten', 'mindestlohn', 'klimaschutz')

## 5. Rationale - WICHTIG!
Fuer jedes Unterthema MUSS ein ausfuehrlicher Rationale geschrieben werden:
- Was gehoert zu diesem Unterthema? (Scope definieren)
- Was gehoert NICHT dazu? (Abgrenzung zu anderen Unterthemen)
- Welche konkreten Forderungen/Massnahmen der Partei gehoeren hierher?
- Der Rationale hilft spaeter beim Wissensextraktion!

Beispiel Rationale fuer "Mietpreisregulierung":
"Dieses Unterthema umfasst alle staatlichen Eingriffe in die Mietpreisgestaltung:
Mietpreisbremse, Mietdeckel, Kappungsgrenzen bei Mieterhoehungen. Die Partei fordert
hier konkret die Verlaengerung der Mietpreisbremse bis 2030 und eine Kappungsgrenze
von 11% in 3 Jahren. NICHT hierher gehoeren: Sozialer Wohnungsbau (eigenes Thema),
Wohngeld (Transferleistungen), Neubaufoerderung (Angebotspolitik)."

# Leitlinien

## Quellenbasiertheit
- Extrahiere NUR was in den Dokumenten steht
- Gib konkrete Zahlen und Massnahmen an wenn vorhanden

## Vollstaendigkeit
- Ziel: ~25 Talking Points insgesamt
- 5-8 Hauptthemen mit je 3-5 Unterthemen"""

RESOLUTION_PROMPT = """Extrahiere ALLE relevanten Themen und Talking Points fuer die folgende Anfrage:

Benutzeranfrage: {query}

Quelldokumente:
{retrieved_chunks}

# Aufgabe
Extrahiere 5-8 Hauptthemen mit insgesamt ~25 Talking Points (Unterthemen).

# Extraktionsanweisungen

## Was extrahieren?
- ALLE Positionen und Forderungen der Partei zum Thema
- Konkrete Massnahmen und Zahlen
- Auch parteispezifische Themen (werden spaeter kombiniert)

## Themenerweiterung - WICHTIG!
Beruecksichtige BENACHBARTE und VERWANDTE Themen zur Benutzeranfrage:
- Bei Klimaschutz → auch Finanzierung, Generationengerechtigkeit, Wirtschaftsfolgen, Technologie
- Bei Rente → auch Generationenvertrag, Arbeitsmarkt, Demografie, Altersarmut
- Bei Migration → auch Arbeitsmarkt, Fachkraefte, Integration, Bildung
- Bei Wirtschaft → auch Arbeitsplaetze, Steuern, Buerokratie, Standort

## Beispiele fuer gute Talking Points
- "Mindestlohn auf 15 Euro erhoehen"
- "Mietpreisbremse verlaengern"
- "CO2-Preis erhoehen"
- "Buergergeld reformieren"
- "Tempolimit 130 einfuehren"

## Rationale - KRITISCH!
Fuer JEDES Unterthema schreibe einen detaillierten Rationale (3-5 Saetze):
1. Was gehoert zu diesem Unterthema?
2. Was gehoert NICHT dazu? (Abgrenzung)
3. Welche konkreten Forderungen/Massnahmen der Partei gehoeren hierher?

Der Rationale wird spaeter verwendet um das Wissen praezise zu extrahieren!

# Bewertung
- importance_score: Wie wichtig ist das Thema fuer diese Partei? (0.0-1.0)
- relevance_to_query: Passt es zur Anfrage? (0.0-1.0)"""


def format_chunks_for_party(
    chunks: list[RetrievedChunk], party_id: str, max_chars: int = 8000
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
