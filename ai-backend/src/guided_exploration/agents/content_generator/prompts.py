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
            "Kurzer, gespraechseinladender Einstieg als Markdown "
            "(ca. 60-90 Woerter). Festes Muster: 1-2 Saetze Kernposition, "
            "danach 2-3 Stichpunkte mit den wichtigsten Forderungen "
            "(je max. 1 Zeile). Keine Ueberschriften, keine "
            "Begruendungsabschnitte. Inline-Zitationen [id]."
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
Generiere KURZE, gespraechseinladende Einstiege zu einem politischen Unterthema.
Dein Text ist NICHT die vollstaendige Zusammenfassung aller Positionen — er ist
der Einstiegspunkt, von dem aus der Nutzer per Rueckfrage in die Tiefe geht.

# Inhaltsstruktur

## 1. Zusammenfassung (summary)
- 2-3 Saetze Ueberblick zum Thema
- Erklaere knapp den Kontext
- Zeige in EINEM Satz die Hauptunterschiede zwischen den Parteien

## 2. Parteipositionen (party_positions) — kompakt, festes Muster!
Fuer JEDE Partei genau EIN kurzer Markdown-Text nach diesem Muster:

1. Ein Einleitungsabsatz: 1-2 Saetze Kernposition mit Inline-Zitation [id].
2. Direkt danach 2-3 Stichpunkte (Bullet-Liste) mit den wichtigsten Forderungen,
   jeder Punkt EINE Zeile, jeweils mit [id].

Beispiel:
```
Mars setzt auf den CO2-Preis als zentrales Klimainstrument. [m-klima-001]

- Emissionshandel auf Verkehr, Gebaeude, Landwirtschaft ausweiten [m-klima-002]
- Gebaeudeenergiegesetz und Flottengrenzwerte abschaffen [m-klima-003]
- Kernkraftwerke als Brueckentechnologie reaktivieren [m-klima-007]
```

Harte Regeln fuer den content-Text:
- Ca. 60-90 Woerter pro Partei
- KEINE Ueberschriften (kein "**Kernposition:**", keine h2/h3)
- KEINE separaten Begruendungsabschnitte ("Warum…", "Begruendung…")
- KEINE Vollstaendigkeit — nur die 2-3 markantesten Forderungen
- Gleiche Struktur fuer jede Partei (konsistent, damit gut vergleichbar)

# Leitlinien

## Quellenbasiertheit
- Nutze AUSSCHLIESSLICH Informationen aus dem bereitgestellten Wissen
- Verwende die exakten citation_ids aus dem Wissenspool

## Knappheit statt Vollstaendigkeit
- Waehle die 2-3 markantesten Forderungen, nicht alle
- Zahlen nur, wenn sie die Position pointiert machen
- Dopplungen zwischen Parteien vermeiden, Kernunterschiede herausstellen

## Strikte Neutralitaet
- Bewerte politische Positionen NICHT
- Vermeide wertende Adjektive
- Stelle alle Parteien gleichwertig dar

## Antwortstil
- Klare, aktive Saetze
- Deutsch
- Keine Meta-Kommentare ("Die Partei argumentiert…", "Laut Programm…")

## 3. Folgefragen (suggested_questions)
Generiere 2-3 kurze Folgefragen, die:
- NICHT bereits durch die Zusammenfassung oder Parteipositionen oben beantwortet werden
- Tiefer in Hintergruende, Begruendungen oder Konsequenzen gehen
- Konkret und praegnant formuliert sind (max 10 Worte)

WICHTIG:
- Die Frage darf NICHT direkt aus dem generierten Text ablesbar sein
- Frage nach dem WARUM, nach Konsequenzen, nach Umsetzungsdetails oder Widerspruechen
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

1. **Parteipositionen** (party_positions): Fuer jede Partei ein kurzer Markdown-Text
   (ca. 60-90 Woerter, festes Muster):
   - 1-2 Saetze Kernposition mit Inline-Zitation [id]
   - 2-3 Stichpunkte mit den wichtigsten Forderungen (je max. 1 Zeile), jeweils mit [id]
   - KEINE Ueberschriften, keine Begruendungsabschnitte, keine langen Listen

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
        if position.positions:
            formatted += "Extrahierte Aussagen:\n"
            for pos_item in position.positions:
                formatted += f"  - {pos_item.position}\n"
                formatted += f'    Zitat: "{pos_item.quote}"\n'
                formatted += f"    Quelle: {pos_item.source_doc}"
                if pos_item.source_page:
                    formatted += f", S. {pos_item.source_page}"
                if pos_item.citation_id:
                    formatted += f" [{pos_item.citation_id}]"
                formatted += "\n"

    return formatted


def format_positions_for_content_prompt(
    positions_by_party: dict, parties_info: dict[str, PartyInfo]
) -> str:
    """Format position-based party positions for the content generation prompt."""
    if not positions_by_party:
        return "Keine Parteipositionen verfuegbar."

    formatted = ""
    for party_id, positions in positions_by_party.items():
        party_name = parties_info.get(
            party_id,
            PartyInfo(
                party_id=party_id, name=party_id.upper(), long_name=party_id.upper()
            ),
        ).name
        formatted += f"\n## {party_name} ({party_id})\n"
        formatted += "Positionen und Forderungen:\n"
        for position in positions:
            formatted += f"  - ({position.position_type}) {position.content}\n"
            if position.quote:
                formatted += f'    Zitat: "{position.quote}"\n'
            if position.citation:
                cit = position.citation
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
