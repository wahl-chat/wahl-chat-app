# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for the main-chat follow-up chip generator.

This prompt mirrors the production wahl.chat quick-reply prompt
(see ``generate_chat_title_and_quick_replies_system_prompt_str`` in
``src/prompts.py``): exactly three replies — slot 1 = direct follow-up,
slot 2 = clarification of a term, slot 3 = switch to a different
campaign topic. No "must be answerable from the surfaced pool" filter.

Used by both BaselineHandler and QuickSummaryHandler — the chips look
identical across study conditions on the main chat surface.
"""

from pydantic import BaseModel, Field


class MainChatFollowUpLLMOutput(BaseModel):
    """LLM output schema for the 3 fixed-slot main-chat quick replies."""

    questions: list[str] = Field(
        ...,
        description=(
            "Genau drei Quick Replies in Reihenfolge: "
            "1) direkte Folgefrage, "
            "2) Begriffs-/Definitionsklärung, "
            "3) Wechsel zu einem anderen Wahlkampfthema. "
            "Pro Reply maximal 7 Wörter, Du-Stil, korrektes Deutsch."
        ),
    )


MAIN_CHAT_FOLLOWUP_PROMPT = """{exploration_goals}

{application_context}

## Bisheriges Gespräch
{conversation_history}

## Letzte Nutzerfrage
{query}

## Letzte Antwort
{response}

## Themenweite Parteipositionen (vollständige Wissensbasis)
Das ist das **gesamte Positions-Inventar** für das aktuelle Thema, gruppiert nach Partei und Sub-Aspekt. Nutze das, um zu erkennen, **welche Aspekte noch nicht** in „Bisheriges Gespräch" oder „Letzte Antwort" auftauchen — genau dort liegt Slot 1.

{topic_positions}

## Für die letzte Frage abgerufene Quellen (eng)
Das sind die Chunks, die für die letzte Bot-Antwort retrieved wurden — Teilmenge des obigen Inventars, nicht der ganze Horizont:

{available_context}

## Deine Aufgabe
Generiere genau 3 Quick Replies, die die Nutzer:in im Sinne der Ziele oben **weiterbringen** — nicht zurück auf das, was schon gesagt wurde. Jede Reply muss einen Schritt vorwärts machen, nicht eine Wiederholung anstoßen.

Die drei Slots bedienen die drei Ziele in fester Reihenfolge:

1. **Erkunden / Vertiefen** — eine konkrete Folgefrage zu einem Aspekt, der in „Themenweite Parteipositionen" auftaucht, aber in „Letzte Antwort" und „Bisheriges Gespräch" noch **nicht** substanziell behandelt wurde. Picke einen *neuen* Aspekt, kein Redundanz-Echo.
2. **Verstehen** — eine Frage nach einem Fachbegriff oder einer unklaren Formulierung aus der letzten Antwort. Wenn der Begriff klar einer Partei gehört, nimm den Parteinamen rein („Was meint <der/die/das> <Partei-Name> mit …?"). Wenn die letzte Antwort keinen erklärungsbedürftigen Begriff enthält, formuliere stattdessen eine Verständnisfrage zur Grundhaltung („Warum will <Partei> X?").
3. **Vergleichen / Wechseln** — ein anderer Wahlkampfthemen-Aspekt aus der Wissensbasis, der den Vergleichshorizont öffnet (z.B. ein Sub-Thema des aktuellen Themas, das noch gar nicht angerissen wurde, oder ein verwandter Aspekt für einen Drei-Parteien-Vergleich).

Form jeder Reply:
- An die Partei(en) gerichtet, im Du-Stil, korrektes Deutsch.
- Maximal 7 Wörter, kurz und prägnant.
- Inhaltlich besonders relevant oder brisant für die genannten Parteien.

## Verboten — strikt
**Keine Rephrase-Fragen.** Schlage NIE eine Frage vor, deren Antwort die letzte Bot-Antwort im Wesentlichen nur **wiederholen oder umformulieren** würde. Konkret heißt das:

- ❌ **Keine „Und Partei X dazu?"-Frage zu einer Partei, die in der letzten Antwort schon einen substanziellen Block bekommen hat** (eigene Karte, eigener Abschnitt, oder mehrere konkrete Forderungen). Wenn Mars in der letzten Antwort schon mit „CO2-Preis erhöhen, Klimageld 320€, …" abgedeckt war, ist „Und wie sieht's bei Mars aus?" verboten — das fragt nach genau dem, was gerade dasteht.
- ❌ **Keine „Wie genau / kannst du das nochmal sagen?"-Frage**, deren konkrete Antwort wortwörtlich oder mit minimalen Umstellungen schon in der letzten Antwort steht.
- ❌ **Keine Frage zu Inhalt, den die Bot-Antwort gerade explizit als nicht im Material vorhanden markiert hat** (z.B. „Wie wollt ihr Erneuerbare ausbauen?", wenn der Bot gerade gesagt hat: dazu liegen keine Aussagen vor). Picke stattdessen einen benachbarten, in „Themenweite Parteipositionen" belegten Aspekt.

**Vor jedem Slot prüfen:**
1. Ist die Antwort auf diese Reply schon in „Letzte Antwort" oder „Bisheriges Gespräch" enthalten? Wenn ja → verwerfen, anderen Aspekt aus „Themenweite Parteipositionen" suchen.
2. Bringt die Reply die Nutzer:in tatsächlich auf etwas Neues (Aspekt, Unterschied, Begriff), das sie noch nicht weiß?

Wenn du für Slot 1 keinen sinnvollen *neuen* Aspekt findest, ohne in den Rephrase-Modus zu fallen, formuliere Slot 1 wie Slot 3 als Wechsel zu einem benachbarten Sub-Thema.
"""
