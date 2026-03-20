# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for content generator agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMCitationRef(BaseModel):
    """Reference to a citation from the resolved knowledge."""

    citation_id: str = Field(..., description="ID der Zitation aus dem Wissenspool")


class LLMPartyPosition(BaseModel):
    """A party position as markdown content."""

    party: str = Field(..., description="Party ID (z.B. 'spd', 'cdu')")
    content: str = Field(
        ...,
        description=(
            "Vollstaendige Darstellung der Parteiposition als Markdown. "
            "Enthaelt: Kernposition, alle konkreten Forderungen/Massnahmen, "
            "Zahlen und Ziele. Nutze Stichpunkte fuer Uebersichtlichkeit. "
            "Inline-Zitationen im Format [id] oder [id1, id2]."
        ),
    )


class ContentGeneratorLLMOutput(BaseModel):
    """LLM output schema for content generation."""

    summary: str = Field(
        ..., description="Neutrale Zusammenfassung des Themas (2-3 Saetze)"
    )
    party_positions: list[LLMPartyPosition] = Field(
        default_factory=list, description="Positionen der Parteien als Markdown"
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description=(
            "2-3 Folgefragen, die der Nutzer stellen koennte um das Thema zu vertiefen. "
            "Kurz und praegnant formuliert."
        ),
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Inhaltsgenerierungsagent fuer politische Bildungsinhalte.

{party_context}

# Aufgabe
Generiere umfassende, neutrale Inhalte zu einem politischen Unterthema.

# Inhaltsstruktur

## 1. Zusammenfassung (summary)
- 2-3 Saetze Ueberblick zum Thema
- Erklaere den Kontext und die gesellschaftliche Relevanz
- Zeige konkret die verschiedenen Ansaetze der Parteien auf

## 2. Parteipositionen (party_positions) - WICHTIG!
Fuer JEDE Partei generiere einen vollstaendigen Markdown-Text (content), der enthaelt:

- **Kernposition**: Was ist die grundsaetzliche Haltung der Partei?
- **Konkrete Forderungen**: Alle spezifischen Massnahmen als Stichpunkte
- **Zahlen und Ziele**: Konkrete Werte, Prozente, Jahreszahlen
- **Begruendungen**: Warum vertritt die Partei diese Position?

Formatierung:
- Nutze Markdown: **fett** fuer wichtige Begriffe, Stichpunkte fuer Listen
- Inline-Zitationen: Nach jedem Fakt [id] oder [id1, id2]
- Struktur: Erst Kernposition, dann Details als Aufzaehlung

Beispiel fuer content:
```
Die Partei setzt sich fuer eine **Erhoehung des Mindestlohns** ein. [12]

Konkrete Forderungen:
- Mindestlohn auf **15 Euro** erhoehen [12]
- Jaehrliche Anpassung an Inflation [13]
- Staerkere Kontrollen gegen Lohndumping [14]

3-5
Begruendung: Die Partei argumentiert, dass ein hoeherer Mindestlohn Armut trotz Arbeit bekaempfe. [12]
```

# Leitlinien

## Quellenbasiertheit
- Nutze AUSSCHLIESSLICH Informationen aus dem bereitgestellten Wissen
- Verwende die exakten citation_ids aus dem Wissenspool
- Gib ALLE konkreten Zahlen und Massnahmen an

## Vollstaendigkeit
- Extrahiere ALLE relevanten Positionen aus dem Wissen
- Lieber zu ausfuehrlich als zu knapp
- Jede konkrete Forderung sollte genannt werden

## Strikte Neutralitaet
- Bewerte politische Positionen NICHT
- Vermeide wertende Adjektive
- Stelle alle Parteien gleichwertig dar

## Antwortstil
- Formuliere verstaendlich und praegnant
- Nutze kurze Saetze
- Generiere Inhalte auf Deutsch

## 3. Folgefragen (suggested_questions)
Generiere 2-3 kurze Folgefragen, die:
- NICHT bereits durch die Zusammenfassung oder Parteipositionen oben beantwortet werden!
- Tiefer in die Hintergruende, Begruendungen oder Konsequenzen der Positionen gehen
- Konkret und praegnant formuliert sind (max 10 Worte)

WICHTIG:
- Die Frage darf NICHT direkt aus dem generierten Text ablesbar sein!
- Frage nach dem WARUM, nach Konsequenzen, nach Umsetzungsdetails oder nach Widerspruechen
- FALSCH: "Welche Partei fordert X?" (wenn X oben steht)
- RICHTIG: "Wie soll die Finanzierung der Klimaziele erfolgen?"
- RICHTIG: "Welche Konflikte gibt es zwischen Wirtschaft und Klimazielen?"
- RICHTIG: "Wie realistisch sind die genannten Zeitplaene?\""""

GENERATION_PROMPT = """Generiere Inhalte fuer folgendes Thema:

Thema: {subtopic_name}
Pfad: {path}

== Extrahierte Parteipositionen ==
{party_positions}

== Verfuegbare Zitationen (ID -> Quelle) ==
{citations}

== Aufgabe ==

Generiere die Inhalte in dieser Reihenfolge:

1. **Parteipositionen** (party_positions): Fuer jede Partei ein vollstaendiger Markdown-Text mit:
   - Kernposition in 1-2 Saetzen
   - Alle konkreten Forderungen als Stichpunkte
   - Zahlen, Ziele, Zeitrahmen
   - Inline-Zitationen [id] nach jedem Fakt

2. **Zusammenfassung** (summary): Wird NACH den Parteipositionen angezeigt.
   Schreibe 2-3 Saetze die die Parteipositionen zusammenfassen:
   - Was sind die KONKRETEN Hauptunterschiede?
   - Wo gibt es Gemeinsamkeiten?
   - Nenne spezifische Zahlen/Massnahmen

   FALSCH: "Die Parteien haben unterschiedliche Ansaetze zu diesem Thema."
   RICHTIG: "Waehrend SPD und Gruene den Mindestlohn auf 15 Euro erhoehen wollen, setzt die FDP auf Tarifautonomie ohne staatliche Vorgaben. Einig sind sich alle Parteien, dass Arbeit sich lohnen muss."

3. **Folgefragen** (suggested_questions): 2-3 kurze Fragen die NICHT bereits \
durch die generierten Parteipositionen und die Zusammenfassung beantwortet werden. \
Frage nach Hintergruenden, Konsequenzen, Umsetzungsdetails oder Widerspruechen. \
NIEMALS Fragen stellen deren Antwort im generierten Text steht!

Verwende NUR die bereitgestellten Zitations-IDs."""


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
        formatted += f"\n## {party_name} ({party_id})\n"
        formatted += f"Zusammenfassung: {position.summary}\n"
        if position.claims:
            formatted += "Extrahierte Aussagen:\n"
            for claim in position.claims:
                formatted += f"  - {claim.claim}\n"
                formatted += f'    Zitat: "{claim.quote}"\n'
                formatted += f"    Quelle: {claim.source_doc}"
                if claim.source_page:
                    formatted += f", S. {claim.source_page}"
                if claim.citation_id:
                    formatted += f" [{claim.citation_id}]"
                formatted += "\n"

    return formatted


def format_claims_for_content_prompt(
    claims_by_party: dict, parties_info: dict[str, PartyInfo]
) -> str:
    """Format claim-based party positions for the content generation prompt."""
    if not claims_by_party:
        return "Keine Parteipositionen verfuegbar."

    formatted = ""
    for party_id, claims in claims_by_party.items():
        party_name = parties_info.get(
            party_id,
            PartyInfo(
                party_id=party_id, name=party_id.upper(), long_name=party_id.upper()
            ),
        ).name
        formatted += f"\n## {party_name} ({party_id})\n"
        formatted += "Positionen und Forderungen:\n"
        for claim in claims:
            formatted += f"  - ({claim.claim_type}) {claim.content}\n"
            if claim.quote:
                formatted += f'    Zitat: "{claim.quote}"\n'
            if claim.citation:
                cit = claim.citation
                formatted += f"    Quelle: {cit.document}"
                if cit.page:
                    formatted += f", S. {cit.page}"
                formatted += f" [{cit.id}]\n"

    return formatted


def format_citations_pool(citations: list) -> str:
    """Format the citation pool for the prompt."""
    if not citations:
        return "Keine Zitationen verfuegbar."

    formatted = ""
    for cit in citations:
        formatted += f"- {cit.id}: {cit.party.upper()}, {cit.document}"
        if cit.section:
            formatted += f", {cit.section}"
        if cit.page:
            formatted += f", S. {cit.page}"
        formatted += "\n"

    return formatted
