# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for knowledge resolver agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.exploration import RetrievedChunk


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMExtractedClaim(BaseModel):
    """A single extracted claim with source quote."""

    claim: str = Field(
        ...,
        description="Die extrahierte Aussage/Forderung/Position in eigenen Worten (1 Satz)",
    )
    quote: str = Field(
        ...,
        description="Das WOERTLICHE Zitat aus dem Quelldokument das diese Aussage belegt",
    )
    chunk_index: int = Field(
        ...,
        description="Index des Quelldokuments [1], [2], etc. aus dem das Zitat stammt",
    )
    claim_type: str = Field(
        ...,
        description=(
            "Typ: 'position' (Grundhaltung), 'measure' (Massnahme), "
            "'target' (Zielwert/Zahl), 'argument' (Begruendung), 'criticism' (Kritik)"
        ),
    )


class LLMSubtopicKnowledge(BaseModel):
    """All extracted knowledge for a single subtopic."""

    subtopic_id: str = Field(..., description="ID des Unterthemas")
    has_content: bool = Field(
        ..., description="True wenn die Partei Inhalte zu diesem Thema hat"
    )
    summary: str = Field(
        default="",
        description="Kurze Zusammenfassung in 1 Satz (nur wenn has_content=True)",
    )
    claims: list[LLMExtractedClaim] = Field(
        default_factory=list,
        description=(
            "ALLE extrahierten Aussagen mit woertlichen Zitaten. "
            "Extrahiere JEDE relevante Aussage aus den Quelldokumenten!"
        ),
    )
    relevant_chunk_indices: list[int] = Field(
        default_factory=list,
        description="Indizes der relevanten Quelldokumente fuer dieses Unterthema [1], [2], etc.",
    )


class PartyKnowledgeLLMOutput(BaseModel):
    """LLM output schema for party knowledge resolution."""

    subtopics: list[LLMSubtopicKnowledge] = Field(
        default_factory=list, description="Extrahiertes Wissen fuer jedes Unterthema"
    )


# =============================================================================
# Query Rewriting Output Schema
# =============================================================================


class SubtopicQuery(BaseModel):
    """Rewritten query for a subtopic."""

    subtopic_id: str = Field(..., description="ID des Unterthemas")
    rag_query: str = Field(
        ...,
        description="Optimierte Suchanfrage fuer RAG (Schluesselwoerter, keine ganzen Saetze)",
    )


class QueryRewriteOutput(BaseModel):
    """Output for query rewriting."""

    queries: list[SubtopicQuery] = Field(
        default_factory=list,
        description="Optimierte Suchanfragen fuer jedes Unterthema",
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Extraktionsagent fuer politische Positionen.

# Kontext
Wahlkontext: {context_name}

# Partei
- ID: {party_id}
- Name: {party_name}
- Vollstaendiger Name: {party_long_name}
{party_description}

# Deine Aufgabe
Extrahiere ALLE Positionen, Forderungen und Massnahmen aus den Quelldokumenten.
Jede Aussage MUSS mit einem woertlichen Zitat aus dem Dokument belegt werden.

# KRITISCH: Vollstaendige Extraktion

Du musst JEDE relevante Aussage extrahieren:
- Jede Forderung ("Wir fordern...", "Wir wollen...")
- Jede Massnahme ("Wir werden...", "Wir setzen uns ein fuer...")
- Jede Zielangabe (Zahlen, Prozente, Jahreszahlen)
- Jede Begruendung ("...um...", "...damit...", "...weil...")
- Jede Kritik ("Das aktuelle System...", "Die Regierung hat...")

# Format fuer jede extrahierte Aussage

1. **claim**: Deine Zusammenfassung der Aussage in einem Satz
2. **quote**: Das WOERTLICHE Zitat aus dem Dokument (copy-paste!)
3. **chunk_index**: Die Nummer des Quelldokuments [1], [2], etc.
4. **claim_type**: position/measure/target/argument/criticism

# Beispiel

Aus Quelldokument [1]: "Wir werden den Mindestlohn auf 15 Euro erhoehen, um Armut trotz Arbeit zu bekaempfen."

Extrahiere ZWEI Claims:
1. claim: "Erhoehung des Mindestlohns auf 15 Euro"
   quote: "Wir werden den Mindestlohn auf 15 Euro erhoehen"
   chunk_index: 1
   claim_type: "measure"

2. claim: "Bekaempfung von Erwerbsarmut als Ziel"
   quote: "um Armut trotz Arbeit zu bekaempfen"
   chunk_index: 1
   claim_type: "argument"

# Regeln

- IMMER woertliche Zitate verwenden - keine Paraphrasen im quote-Feld!
- Lieber zu viele Claims als zu wenige
- Ein Satz kann mehrere Claims enthalten - alle extrahieren!
- Summary ist nur 1 kurzer Satz - die Details stehen in den Claims"""

RESOLUTION_PROMPT = """Extrahiere ALLE Positionen dieser Partei zu den folgenden Unterthemen.

# Unterthemen
{subtopics_list}

# Quelldokumente
{retrieved_chunks}

# Anweisungen

Gehe die Quelldokumente Satz fuer Satz durch und extrahiere JEDE relevante Aussage.

Fuer jedes Unterthema:
1. Pruefe ob die Partei dazu Inhalte hat (has_content)
2. Schreibe eine 1-Satz Zusammenfassung (summary)
3. Extrahiere ALLE Claims mit woertlichen Zitaten

# Was extrahieren?

Extrahiere ALLES was zum Scope des Unterthemas passt:
- Forderungen ("Wir fordern...", "Wir wollen...")
- Massnahmen ("Wir werden...", "Wir setzen uns ein...")
- Ziele und Zahlen (Prozente, Euro-Betraege, Jahreszahlen)
- Begruendungen ("...um...", "...damit...", "...weil...")
- Kritik am Status quo

# WICHTIG

- Das quote-Feld MUSS ein woertliches Zitat sein - copy-paste aus dem Dokument!
- Ein Satz kann mehrere Claims enthalten - alle extrahieren!
- Lieber 20 Claims als 5 - Vollstaendigkeit ist wichtiger als Kuerze!
- Beachte den Scope: nur Aussagen extrahieren die zum Unterthema passen

# Beispiel-Extraktion

Dokumenttext [1]: "Wir werden die Mietpreisbremse bis 2030 verlaengern und die Kappungsgrenze auf 11% senken, um bezahlbares Wohnen zu sichern."

Daraus 3 Claims:
1. claim="Verlaengerung der Mietpreisbremse bis 2030", quote="Wir werden die Mietpreisbremse bis 2030 verlaengern", chunk_index=1, claim_type="measure"
2. claim="Senkung der Kappungsgrenze auf 11%", quote="die Kappungsgrenze auf 11% senken", chunk_index=1, claim_type="target"
3. claim="Bezahlbares Wohnen als Ziel", quote="um bezahlbares Wohnen zu sichern", chunk_index=1, claim_type="argument"

Wenn die Partei zu einem Unterthema keine Inhalte hat: has_content=false, leere claims-Liste.
Gib fuer jedes Unterthema die Indizes der relevanten Chunks in relevant_chunk_indices an."""


# =============================================================================
# Query Rewriting Prompts
# =============================================================================

QUERY_REWRITE_SYSTEM_PROMPT = """Du bist ein Experte fuer Suchanfragen-Optimierung.

Deine Aufgabe ist es, fuer jedes Unterthema eine optimierte Suchanfrage zu erstellen,
die in einem RAG-System (Retrieval Augmented Generation) verwendet wird.

# Regeln fuer gute RAG-Queries

1. **Schluesselwoerter statt Saetze**: "Mindestlohn Erhoehung 15 Euro" statt "Wie hoch soll der Mindestlohn sein?"
2. **Spezifische Begriffe**: Nutze Fachbegriffe die im Wahlprogramm vorkommen wuerden
3. **Kombiniere verwandte Begriffe**: "erneuerbare Energien Solar Wind Photovoltaik"
4. **Keine Fragen**: Queries sind Suchbegriffe, keine Fragen
5. **Deutsch**: Queries muessen auf Deutsch sein

# Beispiele

Unterthema: "Mindestlohn und Loehne"
→ rag_query: "Mindestlohn Lohn Erhoehung Euro Tarifbindung Arbeitnehmer"

Unterthema: "Erneuerbare Energien"
→ rag_query: "erneuerbare Energien Solar Wind Photovoltaik Ausbau Klimaneutral"

Unterthema: "Bezahlbarer Wohnraum"
→ rag_query: "Wohnen Miete bezahlbar Mietpreisbremse sozialer Wohnungsbau"
"""

QUERY_REWRITE_USER_PROMPT = """Erstelle optimierte RAG-Suchanfragen fuer folgende Unterthemen:

{subtopics_list}

Fuer jedes Unterthema:
- Nutze Schluesselwoerter die im Wahlprogramm vorkommen wuerden
- Kombiniere Synonyme und verwandte Begriffe
- Halte die Query kurz aber praezise (5-10 Woerter)
"""


def format_subtopics_list(
    subtopics: list[tuple[str, str, str, str]],
) -> str:
    """Format subtopics for the prompt. Each tuple is (id, name, description, scope)."""
    if not subtopics:
        return "Keine Unterthemen angegeben."

    lines = []
    for item in subtopics:
        # Support both old format (3 elements) and new format (4 elements)
        if len(item) == 4:
            subtopic_id, name, description, scope = item
        else:
            subtopic_id, name, description = item
            scope = ""

        lines.append(f"\n## [{subtopic_id}] {name}")
        lines.append(f"Beschreibung: {description}")
        if scope:
            lines.append(f"Scope: {scope}")

    return "\n".join(lines)


def format_chunks(
    chunks: list[RetrievedChunk],
    party_id: str,
    max_chars: int = 12000,
) -> str:
    """Format retrieved chunks for the prompt."""
    party_chunks = [c for c in chunks if c.party_id == party_id]

    if not party_chunks:
        return "Keine Quelldokumente verfuegbar."

    formatted = ""
    total_chars = 0

    for i, chunk in enumerate(party_chunks, 1):
        content = chunk.content
        # Use document_name from metadata if available, fallback to source_document
        doc_name = chunk.metadata.get("document_name", chunk.source_document)
        source = f"[{doc_name}"
        if chunk.source_section:
            source += f", {chunk.source_section}"
        if chunk.source_page:
            source += f", S. {chunk.source_page}"
        source += "]"

        entry = f"\n[{i}] {source}\n{content}\n"

        if total_chars + len(entry) > max_chars:
            formatted += "\n[...weitere Dokumente abgeschnitten...]\n"
            break

        formatted += entry
        total_chars += len(entry)

    return formatted
