# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt template for the main-chat follow-up chip generator.

Built around the shared ``EXPLORATION_GOALS`` (Erkunden / Verstehen /
Vergleichen). The three chip slots each pursue one of those goals as a
question the participant would ask themselves next — third-person,
user-voice, never addressed to the parties.
"""

from pydantic import BaseModel, Field


class MainChatFollowUpLLMOutput(BaseModel):
    """LLM output schema for the 3 goal-aligned main-chat follow-ups."""

    questions: list[str] = Field(
        ...,
        description=(
            "Genau drei Folgefragen in Reihenfolge: "
            "1) Erkunden (neuer Aspekt), "
            "2) Verstehen (Grundhaltung oder Begriff), "
            "3) Vergleichen (neuer Aspekt für Partei-Vergleich). "
            "In der Stimme der Nutzer:in, dritte Person über die Parteien "
            "(nie Du-Stil an die Parteien), natürliche Länge "
            "(etwa 5–14 Wörter), korrektes Deutsch."
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
Das ist das **gesamte Positions-Inventar** für das aktuelle Thema, gruppiert nach Partei und Sub-Aspekt. Nutze das, um zu erkennen, **welche Aspekte noch nicht** in „Bisheriges Gespräch" oder „Letzte Antwort" auftauchen — genau dort liegt der nächste Schritt.

{topic_positions}

## Für die letzte Frage abgerufene Quellen (eng)
Das sind die Chunks, die für die letzte Bot-Antwort retrieved wurden — Teilmenge des obigen Inventars, nicht der ganze Horizont:

{available_context}

## Deine Aufgabe
Generiere genau 3 Folgefragen-Vorschläge, die unter der letzten Antwort als tippbare Chips erscheinen. Die Vorschläge stehen **in der Stimme der Nutzer:in** — als Fragen, die sie als nächstes selbst stellen würde, um die Parteien-Positionen weiter zu erkunden. Die Nutzer:in spricht *über* die Parteien, nicht *mit* ihnen.

Die drei Slots bedienen die drei Ziele in fester Reihenfolge:

1. **Erkunden** — eine Frage zu einem konkreten Aspekt aus „Themenweite Parteipositionen", der in „Letzte Antwort" und „Bisheriges Gespräch" noch **nicht** substanziell behandelt wurde. Sichtbar machen, was noch unentdeckt ist.
2. **Verstehen** — eine Frage nach der Grundhaltung hinter einer Position („Warum will Venus X?", „Was steckt hinter Saturns Ablehnung von Y?") oder nach einem unklaren Fachbegriff aus der letzten Antwort. Nicht „wie genau", sondern „warum" oder „was steckt dahinter".
3. **Vergleichen** — eine Frage, die die Parteien an einem konkreten Aspekt gegeneinanderstellt, der bisher noch nicht direkt kontrastiert wurde — entweder ein neuer Sub-Aspekt des aktuellen Themas oder ein verwandter Aspekt für einen Mehr-Parteien-Vergleich.

Form jeder Frage:
- **In der Stimme der Nutzer:in.** Dritte Person, wenn von Parteien die Rede ist („Wie steht Mars zu X?", „Worin unterscheiden sich die Konzepte von Venus und Saturn?", „Warum lehnt Mars Y ab?"). **Nicht** im Du-Stil an die Parteien gerichtet — kein „eure", „ihr", „wie seht ihr", „kannst du".
- **Natürliche Länge.** Kein Telegrammstil, aber auch kein Roman — etwa 5–14 Wörter, so wie eine echte Folgefrage klingt.
- **Konkret und inhaltsverankert.** Beziehe dich auf den tatsächlichen Inhalt der letzten Antwort oder einen konkreten Aspekt aus dem Positions-Inventar — keine generischen Floskeln.

## Verboten — strikt
**Keine Du-Stil-Anreden an die Parteien.** Niemals „eure Pläne", „ihr wollt", „wie seht ihr", „kannst du erklären" — die Nutzer:in fragt *über* die Parteien, nicht *zu* den Parteien. Falls du dabei ertappt wirst, formuliere die Frage zwingend in die dritte Person um.

**Keine Rephrase-Fragen.** Schlage NIE eine Frage vor, deren Antwort die letzte Bot-Antwort im Wesentlichen nur **wiederholen oder umformulieren** würde. Konkret:

- ❌ **Keine „Und wie ist es bei Partei X?"-Frage zu einer Partei, die in der letzten Antwort schon einen substanziellen Block bekommen hat** (eigene Karte, eigener Abschnitt, oder mehrere konkrete Forderungen). Wenn Mars in der letzten Antwort schon mit „CO2-Preis erhöhen, Klimageld 320 €, …" abgedeckt war, ist „Wie ist Mars' Position dazu?" verboten — das fragt nach genau dem, was gerade dasteht.
- ❌ **Keine „Wie genau?"-Frage**, deren konkrete Antwort wortwörtlich oder mit minimalen Umstellungen schon in der letzten Antwort steht.
- ❌ **Keine Frage zu Inhalt, den die Bot-Antwort gerade explizit als nicht im Material vorhanden markiert hat** (z. B. „Wie wollen die Parteien Erneuerbare ausbauen?", wenn der Bot gerade gesagt hat: dazu liegen keine Aussagen vor). Picke stattdessen einen benachbarten, in „Themenweite Parteipositionen" belegten Aspekt.

**Vor jedem Slot prüfen:**
1. Ist die Antwort auf diese Frage schon in „Letzte Antwort" oder „Bisheriges Gespräch" enthalten? Wenn ja → verwerfen, anderen Aspekt aus „Themenweite Parteipositionen" suchen.
2. Bringt die Frage die Nutzer:in tatsächlich auf etwas Neues (Aspekt, Unterschied, Grundhaltung), das sie noch nicht weiß?
3. Klingt die Frage so, wie die Nutzer:in sie selbst stellen würde — dritte Person über die Parteien, nicht direkte Anrede an sie?

Wenn du für Slot 1 keinen sinnvollen *neuen* Aspekt findest, ohne in den Rephrase-Modus zu fallen, formuliere Slot 1 wie Slot 3 als Wechsel zu einem benachbarten Sub-Thema.
"""
