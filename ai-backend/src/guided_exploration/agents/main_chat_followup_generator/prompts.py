# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt template for the main-chat follow-up chip generator.

Built around the shared ``EXPLORATION_GOALS``. The generator produces
three follow-up questions in the participant's own voice — third-person
about the parties, never addressed to them. The model picks the mix of
angles itself; no per-slot constraint is imposed.
"""

from pydantic import BaseModel, Field


class MainChatFollowUpLLMOutput(BaseModel):
    """LLM output schema for the three main-chat follow-up chips."""

    questions: list[str] = Field(
        ...,
        description=(
            "Genau drei Folgefragen in der Stimme der Nutzer:in, "
            "dritte Person über die Parteien (nie Du-Stil an die Parteien), "
            "natürliche Länge (etwa 5–14 Wörter), korrektes Deutsch."
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

Du entscheidest, welche Mischung von Folgefragen die Nutzer:in im aktuellen Gesprächsmoment am besten weiterbringt — gemessen an den Zielen oben (Erkunden, Verstehen, Vergleichen). Nutze „Themenweite Parteipositionen" als Horizont für das, was es überhaupt noch zu entdecken gibt, und die letzte Antwort als Ausgangspunkt.

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

**Vor jeder Frage prüfen:**
1. Ist die Antwort auf diese Frage schon in „Letzte Antwort" oder „Bisheriges Gespräch" enthalten? Wenn ja → verwerfen.
2. Bringt die Frage die Nutzer:in tatsächlich auf etwas Neues (Aspekt, Unterschied, Grundhaltung), das sie noch nicht weiß?
3. Klingt die Frage so, wie die Nutzer:in sie selbst stellen würde — dritte Person über die Parteien, nicht direkte Anrede an sie?
"""
