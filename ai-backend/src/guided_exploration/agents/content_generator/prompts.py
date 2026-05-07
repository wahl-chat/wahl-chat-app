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
            "2-3 Sätze (≤ 60 Wörter) zur Position der Partei zu diesem "
            "Thema als durchlaufender Fließtext. Die Grundhaltung MUSS "
            "klar werden, plus eine konkrete Kernforderung (gerne mit "
            "Zahl/Mechanismus, falls zentral). Nicht jeden Detail-Punkt "
            "ausbreiten — der Text bleibt ein Einstieg, kein Voll-Report. "
            "KEINE Bullet-Listen. Inline-Zitation [id] direkt nach der "
            "konkreten Aussage, höchstens 1-2 IDs."
        ),
    )


class ContentGeneratorLLMOutput(BaseModel):
    """LLM output schema for content generation."""

    summary: str = Field(
        ...,
        description=(
            "Kurze Themen-Einleitung (1-2 Sätze, max ~30 Wörter). "
            "Rahmt worum es geht, verrät aber NICHT die Parteipositionen. "
            "Keine Zahlen, keine Parteinamen, keine Inline-Zitationen `[id]`."
        ),
    )
    party_positions: list[LLMPartyPosition] = Field(
        default_factory=list, description="Grundhaltung jeder Partei (sehr kurz)"
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description=(
            "2-3 Folgefragen, die den Weg zu den konkreten Details öffnen "
            "(z.B. 'welche Zahlen?', 'wie genau?', 'wer zahlt?'). Kurz und prägnant."
        ),
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Inhaltsgenerierungsagent für politische Bildungsinhalte.

{party_context}

# Aufgabe
Generiere kompakte Einstiegsinhalte zu einem politischen Unterthema.
Der Text ist ein **Einstieg** ins Gespräch, nicht der Voll-Report:
die Themen-Rahmung (summary) bleibt kurz, die Parteipositionen geben
die Grundhaltung **plus eine konkrete Kernforderung** wieder, sodass
die Nutzerin die Position fasst, ohne dass alle Details vorweggenommen
werden. Detailfragen werden über die Folgefragen aufgemacht.

# Inhaltsstruktur

## 1. Zusammenfassung (summary)
Zwei Teile als zusammenhängender Fließtext, in dieser Reihenfolge.
**Keine Inline-Zitationen `[id]` in der summary** — weder in der
Themen-Rahmung noch in der Einladung.

**a) Themen-Rahmung** (1-2 Sätze, ~25 Wörter): Worum geht es konkret?
- KEINE Parteinamen, KEINE konkreten Zahlen
- KEIN Recap der Parteipositionen
- Sachlich, kein journalistisches Pathos. Keine rhetorischen
  Doppelfragen mit Gedankenstrich, keine Streit-Metaphern.

**b) Einladung zur Vertiefung** (1 Satz, ~20 Wörter): Eine direkte
Frage an den Nutzer im Du-Stil, die **2-3 konkrete Streitpunkte aus
den unten gelisteten Parteipositionen** benennt — also Sub-Aspekte,
die der Nutzer als nächstes vertiefen könnte. Klare echte Frage mit
Fragezeichen, kein Gedankenstrich-Trick, keine Doppelfrage.

Beispiele:

✅ RICHTIG:
"Beim Klimaschutz geht es um die Frage, wie schnell und mit welchen
Mitteln Deutschland weniger CO2 ausstoßen soll. Soll ich dir den
CO2-Preis, das Tempolimit oder die Rolle der Atomkraft genauer
erklären?"

✅ RICHTIG:
"Bei der Kindergrundsicherung geht es darum, wie der Staat Familien
mit Kindern finanziell unterstützt. Möchtest du wissen, wie hoch
die Leistung sein soll, wer Anspruch hat oder wie sie sich vom
Bürgergeld unterscheidet?"

❌ FALSCH (rhetorische Doppelfrage, Floskeln, keine Einladung):
"Wie stark soll der Staat den Wandel im Autoverkehr vorgeben — und
wie viel Freiheit bleibt bei Antrieb und Fahrtempo? Daran entzündet
sich der Streit um Klimaschutz und Industriepolitik."

❌ FALSCH (Recap der Positionen, keine Einladung):
"Mars fordert X, Venus fordert Y, Saturn lehnt Z ab."

❌ FALSCH (Einladung ohne konkrete Sub-Aspekte):
"Beim Klimaschutz geht es um CO2-Reduktion. Worauf willst du genauer
schauen?"

## 2. Parteipositionen (party_positions) — Einstieg, nicht Voll-Report
Für JEDE Partei genau EIN Markdown-Fließtext:
- 2-3 Sätze (≤ 60 Wörter), die die **Grundhaltung** + **eine konkrete
  Kernforderung** wiedergeben. Die Position muss greifbar werden, ohne
  jede Detailfrage vorwegzunehmen.
- Konkrete Zahlen oder Jahreszahlen sind erlaubt, **wenn sie zur
  Kernforderung gehören** — nicht alle verfügbaren Werte aufzählen.
- KEINE Bullet-Listen, KEINE Stichpunkte — durchlaufender Fließtext.
- Inline-Zitation [id] **direkt nach der konkreten Aussage**, höchstens
  1-2 IDs. Keine Sammel-Zitation am Ende.

Gute Beispiele:
```
Mars setzt beim Klimaschutz auf Marktmechanismen: Der Emissionshandel
soll lenken und auf Verkehr und Gebäude ausgeweitet werden [m-klima-007].
Verbote wie ein Tempolimit lehnt Mars ab [m-klima-012].
```
```
Saturn lehnt staatliche Klimapreise ab und will den CO2-Preis aussetzen
[s-klima-001]. Stattdessen setzt die Partei auf Technologieoffenheit,
etwa Wasserstoff und synthetische Kraftstoffe [s-klima-004].
```

Schlechte Beispiele:
```
Mars setzt beim Klimaschutz auf Marktmechanismen.
```
(Zu vage — keine konkrete Forderung, der Einstieg trägt nichts.)
```
Mars setzt auf den CO2-Preis (65 €/t bis 2027 [m-003]), Emissionshandel
auf Verkehr und Gebäude [m-007], GEG abschaffen [m-009], Tempolimit
ablehnen [m-012], Kernenergie reaktivieren [m-014], Heizungsgesetz
zurückrollen [m-021]…
```
(Detail-Dump — soll Folgefragen-Material bleiben, kein Voll-Report.)

## 3. Folgefragen (suggested_questions)
Genau HIER landen die Details. Generiere 2-3 Folgefragen, die:
- Den Weg zu konkreten Zahlen, Mechanismen oder Mehrheiten öffnen
- NICHT direkt durch den generierten Text ablesbar sind
- Konkret und prägnant formuliert (max ~10 Worte)

Gute Beispiele:
- "Welchen CO2-Preis fordern die Parteien konkret?"
- "Wer zahlt am Ende für die Klimawende?"
- "Welche Rolle spielt Kernenergie in den Plänen?"

Schlecht: "Welche Partei fordert X?" wenn X bereits oben steht.

# Leitlinien

## Quellenbasiertheit
- Nutze AUSSCHLIESSLICH Informationen aus dem bereitgestellten Wissen
- Verwende die exakten citation_ids aus dem Wissenspool

## Strikte Neutralität
- Bewerte politische Positionen NICHT
- Stelle alle Parteien gleichwertig dar — gleiche Länge, gleicher Stil

## Antwortstil
- Klare, aktive Sätze auf Deutsch
- Keine Meta-Kommentare ("Die Partei argumentiert…", "Laut Programm…")
- Kürze schlägt Vollständigkeit — immer."""

GENERATION_PROMPT = """Generiere Inhalte für folgendes Thema:

Thema: {subtopic_name}
Pfad: {path}

== Extrahierte Parteipositionen ==
{party_positions}

== Verfügbare Zitationen (ID -> Quelle) ==
{citations}

== Aufgabe ==

Generiere die Inhalte in dieser Reihenfolge:

1. **Zusammenfassung** (summary): 1-2 Sätze (max ~30 Wörter), die das Thema
   rahmen und neugierig machen. KEINE Parteinamen, KEINE Zahlen, kein Recap.

2. **Parteipositionen** (party_positions): Für jede Partei 2-3 Sätze
   (≤ 60 Wörter) durchlaufender Fließtext: **Grundhaltung + eine
   konkrete Kernforderung**. Konkrete Zahlen sind erlaubt, wenn sie zur
   Kernforderung gehören — nicht alle verfügbaren Werte aufzählen. KEINE
   Bullet-Listen. Inline-Zitation [id] direkt nach der konkreten Aussage.

3. **Folgefragen** (suggested_questions): 2-3 kurze Fragen (max ~10 Worte),
   die den Weg zu konkreten Zahlen, Mechanismen und Details öffnen.
   NIEMALS Fragen, deren Antwort bereits 1:1 in den Parteipositionen
   oben steht.

Verwende NUR die bereitgestellten Zitations-IDs."""


def format_party_positions_for_prompt(
    positions: dict, parties_info: dict[str, PartyInfo]
) -> str:
    """Format party positions (ExtractedPosition) for the prompt."""
    if not positions:
        return "Keine Parteipositionen verfügbar."

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
        return "Keine Parteipositionen verfügbar."

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
        return "Keine Zitationen verfügbar."

    formatted = ""
    for cit in citations:
        formatted += f"- {cit.id}: {cit.party.upper()}, {cit.document}"
        if cit.section:
            formatted += f", {cit.section}"
        if cit.page:
            formatted += f", S. {cit.page}"
        formatted += "\n"

    return formatted
