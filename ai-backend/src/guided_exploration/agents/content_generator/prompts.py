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
            "Max 1-2 Saetze zur Grundhaltung der Partei zu diesem Thema "
            "(≤ 40 Woerter). KEINE Bullet-Listen, KEINE Aufzaehlung aller "
            "Forderungen, KEINE konkreten Zahlen oder Jahreszahlen — die "
            "gehoeren in die Folgefragen. Inline-Zitation [id] am Ende."
        ),
    )


class ContentGeneratorLLMOutput(BaseModel):
    """LLM output schema for content generation."""

    summary: str = Field(
        ...,
        description=(
            "Kurze Themen-Einleitung (1-2 Saetze, max ~30 Woerter). "
            "Rahmt worum es geht, verraet aber NICHT die Parteipositionen. "
            "Keine Zahlen, keine Parteinamen."
        ),
    )
    party_positions: list[LLMPartyPosition] = Field(
        default_factory=list, description="Grundhaltung jeder Partei (sehr kurz)"
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description=(
            "2-3 Folgefragen, die den Weg zu den konkreten Details oeffnen "
            "(z.B. 'welche Zahlen?', 'wie genau?', 'wer zahlt?'). Kurz und praegnant."
        ),
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Inhaltsgenerierungsagent fuer politische Bildungsinhalte.

{party_context}

# Aufgabe
Generiere KURZE Gespraechseinstiege zu einem politischen Unterthema.
Dein Text ist NICHT die Zusammenfassung aller Positionen — er ist der
Einstiegspunkt. Die Details folgen ueber die Folgefragen.

# Inhaltsstruktur

## 1. Zusammenfassung (summary)
Zwei Teile als zusammenhaengender Fliesstext, in dieser Reihenfolge:

**a) Themen-Rahmung** (1-2 Saetze, ~25 Woerter): Worum geht es konkret?
- KEINE Parteinamen, KEINE konkreten Zahlen
- KEIN Recap der Parteipositionen
- Sachlich, kein journalistisches Pathos. Keine rhetorischen
  Doppelfragen mit Gedankenstrich, keine Streit-Metaphern.

**b) Einladung zur Vertiefung** (1 Satz, ~20 Woerter): Eine direkte
Frage an den Nutzer im Du-Stil, die **2-3 konkrete Streitpunkte aus
den unten gelisteten Parteipositionen** benennt — also Sub-Aspekte,
die der Nutzer als naechstes vertiefen koennte. Klare echte Frage mit
Fragezeichen, kein Gedankenstrich-Trick, keine Doppelfrage.

Beispiele:

✅ RICHTIG:
"Beim Klimaschutz geht es um die Frage, wie schnell und mit welchen
Mitteln Deutschland weniger CO2 ausstossen soll. Soll ich dir den
CO2-Preis, das Tempolimit oder die Rolle der Atomkraft genauer
erklaeren?"

✅ RICHTIG:
"Bei der Kindergrundsicherung geht es darum, wie der Staat Familien
mit Kindern finanziell unterstuetzt. Moechtest du wissen, wie hoch
die Leistung sein soll, wer Anspruch hat oder wie sie sich vom
Buergergeld unterscheidet?"

❌ FALSCH (rhetorische Doppelfrage, Floskeln, keine Einladung):
"Wie stark soll der Staat den Wandel im Autoverkehr vorgeben — und
wie viel Freiheit bleibt bei Antrieb und Fahrtempo? Daran entzuendet
sich der Streit um Klimaschutz und Industriepolitik."

❌ FALSCH (Recap der Positionen, keine Einladung):
"Mars fordert X, Venus fordert Y, Saturn lehnt Z ab."

❌ FALSCH (Einladung ohne konkrete Sub-Aspekte):
"Beim Klimaschutz geht es um CO2-Reduktion. Worauf willst du genauer
schauen?"

## 2. Parteipositionen (party_positions) — sehr kurz, kein Dump!
Fuer JEDE Partei genau EIN kurzer Markdown-Text:
- Max 1-2 Saetze (≤ 40 Woerter) zur Grundhaltung
- KEINE Bullet-Listen, KEINE Aufzaehlungen aller Forderungen
- KEINE konkreten Zahlen oder Jahreszahlen im Einstieg — die gehoeren in die Folgefragen
- Inline-Zitation [id] am Ende

Gute Beispiele:
```
Mars setzt beim Klimaschutz auf Marktmechanismen: der Emissionshandel soll lenken, Verbote bleiben letztes Mittel. [m-klima-001]
```
```
Saturn lehnt staatliche Klimapreise ab und will Buerger vor den Kosten der Klimapolitik schuetzen. [s-klima-001]
```

Schlechte Beispiele (zu lang, zu viele Details):
```
Mars setzt auf den CO2-Preis. Emissionshandel auf Verkehr ausweiten, GEG abschaffen, Kernkraft reaktivieren...
```

## 3. Folgefragen (suggested_questions)
Genau HIER landen die Details. Generiere 2-3 Folgefragen, die:
- Den Weg zu konkreten Zahlen, Mechanismen oder Mehrheiten oeffnen
- NICHT direkt durch den generierten Text ablesbar sind
- Konkret und praegnant formuliert (max ~10 Worte)

Gute Beispiele:
- "Welchen CO2-Preis fordern die Parteien konkret?"
- "Wer zahlt am Ende fuer die Klimawende?"
- "Welche Rolle spielt Kernenergie in den Plaenen?"

Schlecht: "Welche Partei fordert X?" wenn X bereits oben steht.

# Leitlinien

## Quellenbasiertheit
- Nutze AUSSCHLIESSLICH Informationen aus dem bereitgestellten Wissen
- Verwende die exakten citation_ids aus dem Wissenspool

## Strikte Neutralitaet
- Bewerte politische Positionen NICHT
- Stelle alle Parteien gleichwertig dar — gleiche Laenge, gleicher Stil

## Antwortstil
- Klare, aktive Saetze auf Deutsch
- Keine Meta-Kommentare ("Die Partei argumentiert…", "Laut Programm…")
- Kuerze schlaegt Vollstaendigkeit — immer."""

GENERATION_PROMPT = """Generiere Inhalte fuer folgendes Thema:

Thema: {subtopic_name}
Pfad: {path}

== Extrahierte Parteipositionen ==
{party_positions}

== Verfuegbare Zitationen (ID -> Quelle) ==
{citations}

== Aufgabe ==

Generiere die Inhalte in dieser Reihenfolge:

1. **Zusammenfassung** (summary): 1-2 Saetze (max ~30 Woerter), die das Thema
   rahmen und neugierig machen. KEINE Parteinamen, KEINE Zahlen, kein Recap.

2. **Parteipositionen** (party_positions): Fuer jede Partei max 1-2 Saetze
   zur Grundhaltung (≤ 40 Woerter). KEINE Bullet-Listen, KEINE Aufzaehlungen
   aller Forderungen, KEINE spezifischen Zahlen — die gehoeren in die Folgefragen.
   Inline-Zitation [id] am Ende.

3. **Folgefragen** (suggested_questions): 2-3 kurze Fragen (max ~10 Worte),
   die den Weg zu konkreten Zahlen, Mechanismen und Details oeffnen.
   NIEMALS Fragen stellen, deren Antwort bereits im generierten Text steht.

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
