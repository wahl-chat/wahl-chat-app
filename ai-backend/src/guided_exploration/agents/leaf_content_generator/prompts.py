# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for leaf content generator agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo


# =============================================================================
# LLM Output Schema
# =============================================================================


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
            "KEINE Bullet-Listen. Verwende `[PARTY_BADGE:id]` statt des "
            "Parteinamens, wann immer du die Partei in einem Satz "
            "erwähnst — die Frontend-Renderung ersetzt das durch eine "
            "Inline-Pille. Inline-Zitation [id] direkt nach der konkreten "
            "Aussage — pro Forderung höchstens 1 ID, niemals zwei IDs "
            "nebeneinander gestapelt. Insgesamt höchstens 1-2 IDs im "
            "ganzen Text."
        ),
    )


class LeafContentGeneratorLLMOutput(BaseModel):
    """LLM output schema for leaf content generation."""

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


SYSTEM_PROMPT = """{exploration_goals}

{application_context}

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
- Verwende `[PARTY_BADGE:id]` statt des Parteinamens, wann immer du die
  Partei in einem Satz nennst — das Frontend rendert daraus die
  Inline-Pille. Die `id` muss exakt der Partei-ID aus dem
  party-Feld bzw. der Parteiliste entsprechen.
- Inline-Zitation [id] **direkt nach der konkreten Aussage**, höchstens
  1-2 IDs. Keine Sammel-Zitation am Ende.

Gute Beispiele (Beispiel-IDs `mars` und `saturn`):
```
[PARTY_BADGE:mars] setzt beim Klimaschutz auf Marktmechanismen. Der
Emissionshandel soll auf Verkehr und Gebäude ausgeweitet werden
[m-klima-007]. Ein Tempolimit lehnt die Partei dagegen ab
[m-klima-012].
```
```
[PARTY_BADGE:saturn] lehnt staatliche Klimapreise ab. Konkret soll
der CO2-Preis ausgesetzt werden [s-klima-001]. Stattdessen sollen
Wasserstoff und synthetische Kraftstoffe gefördert werden
[s-klima-004].
```

Schlechte Beispiele:
```
Mars setzt beim Klimaschutz auf Marktmechanismen.
```
(Parteiname statt Badge — und zu vage, keine konkrete Forderung.)
```
[PARTY_BADGE:mars] setzt auf den CO2-Preis (65 €/t bis 2027 [m-003]),
Emissionshandel auf Verkehr und Gebäude [m-007], GEG abschaffen
[m-009], Tempolimit ablehnen [m-012], Kernenergie reaktivieren
[m-014], Heizungsgesetz zurückrollen [m-021]…
```
(Detail-Dump — sechs Forderungen in einem Satz; das gehört in die
Folgefragen, nicht in den Einstieg. Die Zitationsform an sich (jede
ID inline an ihrer Forderung) wäre sauber — das Problem ist allein
die Menge: Einstieg ≠ Voll-Report.)

## 3. Folgefragen (suggested_questions)
Genau HIER landen die Details. Generiere 2-3 Folgefragen, die der Nutzer
realistisch als Nächstes anklicken würde. Mische zwei Richtungen:
- **Vertiefung** einer in der Zusammenfassung erwähnten Forderung
  (Zahl, Mechanismus, Begründung).
- **Benachbarter Aspekt** dieses Unterthemas, der oben noch nicht
  behandelt wurde, aber in den Parteipositionen der Wissensbasis
  vorkommt — z.B. nach CO2-Preis-Einstieg eine Frage zu CBAM /
  EU-Außengrenze, nach Verbrennerverbot eine zu Pendlerpauschale
  oder Inlandsflügen.

Anforderungen:
- NICHT direkt durch den generierten Text ablesbar
- Konkret und prägnant (max ~10 Worte)
- Im Geltungsbereich dieses Unterthemas bleiben — kein Sprung ins
  Oberthema oder andere Politikfeld

Gute Beispiele (Mischung Vertiefung + Nachbar):
- "Welchen CO2-Preis fordern die Parteien konkret?" (Vertiefung)
- "Was passiert an der EU-Außengrenze?" (benachbarter Aspekt — CBAM)
- "Und Inlandsflüge — fallen die unter den CO2-Preis?" (benachbart)
- "Wer zahlt am Ende für die Klimawende?" (Vertiefung)

Schlecht: "Welche Partei fordert X?" wenn X bereits oben steht.

## Quellenbasiertheit
- Nutze AUSSCHLIESSLICH Informationen aus dem bereitgestellten Wissen
- Verwende die exakten citation_ids aus dem Wissenspool

## Antwortstil
- Keine Meta-Kommentare ("Die Partei argumentiert…", "Laut Programm…")
- Kürze schlägt Vollständigkeit — immer.
- Stelle alle Parteien gleichwertig dar — gleiche Länge, gleicher Stil.

{citation_directive}

{base_rules}"""

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
   Bullet-Listen. Verwende `[PARTY_BADGE:id]` statt des Parteinamens
   für inline Parteierwähnungen. Inline-Zitation [id] direkt nach der
   konkreten Aussage — pro Forderung höchstens 1 ID, niemals zwei IDs
   nebeneinander gestapelt.

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
