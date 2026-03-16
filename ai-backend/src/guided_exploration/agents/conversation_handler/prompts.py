# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for conversation handler agent."""

from uuid import uuid4

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.exploration import RetrievedChunk


# =============================================================================
# LLM Output Schema
# =============================================================================


class ConversationLLMOutput(BaseModel):
    """LLM output schema for conversation handling."""

    response: str = Field(
        ...,
        description=(
            "Die generierte Antwort im Markdown-Format. "
            "KEINE Zitations-IDs im Text - nur sauberer, lesbarer Text."
        ),
    )
    cited_sources: list[str] = Field(
        default_factory=list,
        description="IDs der verwendeten Zitationen (nur hier, nicht im response-Text)",
    )
    suggested_followups: list[str] = Field(
        default_factory=list, description="1-2 Vorschlaege fuer Folgefragen"
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Konversationsagent fuer politische Bildung.

{party_context}

# Aufgabe
Beantworte Folgefragen innerhalb eines politischen Themas neutral und quellenbasiert.

# Antwortstruktur

## 1. Antworten generieren
- Basierend auf dem aufbereiteten Wissen antworten
- Auf die spezifische Frage eingehen
- **Markdown-Formatierung verwenden** (Ueberschriften, Listen, Fettdruck)

## 2. Zitieren
- Gib verwendete Zitations-IDs NUR im cited_sources Feld an
- NIEMALS Zitations-IDs im Antworttext einbetten
- Der Antworttext soll sauber lesbar sein

## 3. Kontext beruecksichtigen
- Vorherige Nachrichten einbeziehen
- Keine Wiederholungen
- Auf den Gespraechsverlauf eingehen

## 4. Folgefragen vorschlagen
- 1-2 moegliche Vertiefungsfragen anbieten
- Zum Thema passend, neue Aspekte aufzeigen

# Leitlinien

## Quellenbasiertheit
- Nutze AUSSCHLIESSLICH Informationen aus dem bereitgestellten Wissen
- Gib konkrete Zahlen und Daten an, wenn vorhanden
- Fokussiere dich auf die relevanten Informationen

## Strikte Neutralitaet
- Bewerte politische Positionen NICHT
- Vermeide wertende Adjektive und Formulierungen
- Gib KEINE Wahlempfehlungen
- Formuliere Aeusserungen von Parteien im Konjunktiv (z.B. "Die SPD betont, dass...")

## Transparenz
- Kennzeichne Unsicherheiten klar
- Unterscheide zwischen Fakten und Interpretationen
- Gib zu, wenn Informationen nicht verfuegbar sind

## Antwortstil
- Antworte klar, praegnant und quellengestuetzt
- Nutze kurze Saetze und leicht verstaendliches Deutsch
- Erklaere Fachbegriffe kurz
- Antworte auf Deutsch
- Verwende Markdown fuer Struktur und Lesbarkeit"""

CONVERSATION_PROMPT = """Frage: {message}

Themenkontext: {subtopic_name}

== Vorherige Nachrichten ==
{conversation_history}

== Quelltexte aus den Wahlprogrammen ==
{chunks}

== Aufgabe ==

Beantworte GENAU die gestellte Frage!
- Nutze die Quelltexte um spezifische Details zu finden
- Zitiere inline mit [index] nach jedem Fakt
- Sei direkt und praegnant
- Schlage 1-2 Folgefragen vor"""


def format_conversation_history(messages: list, max_messages: int = 5) -> str:
    """Format conversation history for the prompt."""
    if not messages:
        return "Keine vorherigen Nachrichten."

    formatted = ""
    for msg in messages[-max_messages:]:
        role_label = "Nutzer" if msg.role.value == "user" else "Assistent"
        content = (
            msg.content if isinstance(msg.content, str) else "[Strukturierter Inhalt]"
        )
        formatted += f"{role_label}: {content}\n"

    return formatted


def format_party_positions_for_prompt(
    positions: dict, parties_info: dict[str, PartyInfo]
) -> str:
    """Format party positions (ExtractedPosition) for the prompt."""
    if not positions:
        return "Keine Parteipositionen verfuegbar."

    formatted = ""
    for party_id, position in positions.items():
        party_name = parties_info.get(
            party_id,
            PartyInfo(
                party_id=party_id, name=party_id.upper(), long_name=party_id.upper()
            ),
        ).name
        formatted += f"\n{party_name} ({party_id}):\n"
        if position.summary:
            formatted += f"  Zusammenfassung: {position.summary}\n"
        if position.claims:
            formatted += "  Kernaussagen:\n"
            for claim in position.claims:
                formatted += f"    - {claim.claim}"
                if claim.citation_id:
                    formatted += f" [{claim.citation_id}]"
                formatted += "\n"

    return formatted


def format_claims_with_indices(
    positions: dict,
    parties_info: dict[str, PartyInfo],
) -> tuple[str, dict[int, str]]:
    """Format claims from party positions with indices for citation.

    Returns:
        A tuple of (formatted string, index-to-citation_id mapping)
        The LLM uses simple indices [0], [1], etc. which we map back to citation IDs.
    """
    if not positions:
        return "Keine Quellenangaben verfuegbar.", {}

    formatted = ""
    index_to_citation_id: dict[int, str] = {}
    current_index = 0

    for party_id, position in positions.items():
        party_name = parties_info.get(
            party_id,
            PartyInfo(
                party_id=party_id, name=party_id.upper(), long_name=party_id.upper()
            ),
        ).name

        if not position.claims:
            continue

        formatted += f"\n## {party_name}\n"
        for claim in position.claims:
            formatted += f"[{current_index}] {claim.claim}"
            if claim.quote:
                formatted += f' ("{claim.quote[:100]}...")'
            formatted += "\n"

            if claim.citation_id:
                index_to_citation_id[current_index] = claim.citation_id
            current_index += 1

    return formatted, index_to_citation_id


# =============================================================================
# Streaming Prompts (with party markers for frontend display)
# =============================================================================

STREAMING_SYSTEM_PROMPT = """Du bist ein hilfreicher Assistent fuer politische Bildung.

{party_context}

# Deine Aufgabe
Beantworte Nutzerfragen natuerlich und direkt - wie in einem Gespraech.

# WICHTIG: Antworte auf die KONKRETE Frage!

- Wenn jemand fragt "Was gehoert fuer die Gruenen zu erneuerbaren Energien?" → Liste konkret auf, welche Energiequellen die Gruenen als erneuerbar betrachten
- Wenn jemand fragt "Wo beantrage ich Briefwahl?" → Erklaere den Prozess direkt
- Wenn jemand fragt "Warum?" → Erklaere die Gruende
- KEINE generischen Zusammenfassungen wenn eine spezifische Antwort gefragt ist!

# Antwortstil

- Antworte DIREKT auf die Frage - keine Einleitungen wie "Hier ist eine Uebersicht..."
- Schreibe natuerlich, wie du einem Freund erklaeren wuerdest
- Wenn die Antwort kurz sein kann, sei kurz
- Nur strukturieren (Listen, Ueberschriften) wenn es wirklich hilft

# Bei EINER Partei
- Antworte direkt ohne Marker
- Konzentriere dich auf die gefragte Information

# Bei MEHREREN Parteien
Strukturiere mit Markern:

[PARTY:partei_id]
Inhalt...
[/PARTY:partei_id]

Partei-IDs: spd, cdu, gruene, fdp, linke, afd, bsw

# Zitierweise
- Nach Fakten: [0], [1], [2] etc.
- Mehrere: [0, 2]

# Grundregeln
- NUR Informationen aus dem bereitgestellten Wissen verwenden
- Neutral bleiben - keine Wertungen oder Empfehlungen
- Unsicherheiten klar benennen
- Wenn etwas nicht im Wissen steht: ehrlich sagen"""

STREAMING_USER_PROMPT = """Frage: {message}

Themenkontext: {subtopic_name}

== Vorherige Nachrichten ==
{conversation_history}

== Quelltexte aus den Wahlprogrammen ==
{chunks}

== WICHTIG ==
Beantworte GENAU die gestellte Frage!
- Nutze die Quelltexte um spezifische Details zu finden
- Zitiere mit [index] nach jedem Fakt (z.B. [0], [1])
- Bei mehreren Parteien: [PARTY:id]...[/PARTY:id] verwenden
"""


def format_chunks_for_conversation(
    party_chunks: dict[str, list[RetrievedChunk]],
    parties_info: dict[str, PartyInfo],
    max_chars: int = 8000,
) -> tuple[str, dict[int, RetrievedChunk]]:
    """
    Format chunks from all parties for conversation prompts.

    Returns:
        Tuple of (formatted string, index-to-chunk mapping for citations)
    """
    if not party_chunks:
        return "Keine Quelltexte verfuegbar.", {}

    formatted = ""
    index_to_chunk: dict[int, RetrievedChunk] = {}
    current_index = 0
    total_chars = 0

    for party_id, chunks in party_chunks.items():
        if not chunks:
            continue

        party_name = parties_info.get(
            party_id,
            PartyInfo(
                party_id=party_id, name=party_id.upper(), long_name=party_id.upper()
            ),
        ).name

        formatted += f"\n## {party_name}\n"

        for chunk in chunks:
            # Truncate very long chunks
            content = chunk.content
            if len(content) > 500:
                content = content[:500] + "..."

            # Build source info
            doc_name = chunk.metadata.get("document_name", chunk.source_document)
            source = f"[{doc_name}"
            if chunk.source_section:
                source += f", {chunk.source_section}"
            if chunk.source_page is not None:
                source += f", S. {chunk.source_page + 1}"
            source += "]"

            entry = f"[{current_index}] {source}\n{content}\n\n"

            if total_chars + len(entry) > max_chars:
                formatted += "\n[...weitere Quelltexte abgeschnitten...]\n"
                break

            formatted += entry
            index_to_chunk[current_index] = chunk
            current_index += 1
            total_chars += len(entry)

    return formatted, index_to_chunk


def create_citation_from_chunk(chunk: RetrievedChunk, subtopic_id: str) -> Citation:
    """Create a Citation object from a RetrievedChunk."""
    doc_name = chunk.metadata.get("document_name", chunk.source_document)
    citation_id = f"{chunk.party_id}-{subtopic_id}-{uuid4().hex[:8]}"

    return Citation(
        id=citation_id,
        party=chunk.party_id,
        document=doc_name,
        section=chunk.source_section,
        page=chunk.source_page + 1 if chunk.source_page is not None else None,
        document_publish_date=chunk.metadata.get("document_publish_date"),
        url=chunk.metadata.get("url"),
    )


def build_chunk_citation_mapping(
    party_chunks: dict[str, list[RetrievedChunk]],
    parties_info: dict[str, PartyInfo],
    subtopic_id: str,
) -> tuple[str, dict[int, str], list[Citation]]:
    """
    Build chunk text, index-to-citation_id mapping, and citation list.

    Returns:
        Tuple of (formatted chunks text, index-to-citation_id dict, list of citations)
    """
    chunks_text, index_to_chunk = format_chunks_for_conversation(
        party_chunks, parties_info
    )

    index_to_citation_id: dict[int, str] = {}
    citations: list[Citation] = []

    for idx, chunk in index_to_chunk.items():
        citation = create_citation_from_chunk(chunk, subtopic_id)
        index_to_citation_id[idx] = citation.id
        citations.append(citation)

    return chunks_text, index_to_citation_id, citations
