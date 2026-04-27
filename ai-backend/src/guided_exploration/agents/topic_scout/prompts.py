# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for topic scout agent."""

from pydantic import BaseModel, Field


class LLMTopicDirection(BaseModel):
    """LLM output schema for a single topic direction."""

    name: str = Field(
        ...,
        description="Kurzer, prägnanter Name für die Richtung (3-6 Wörter)",
    )
    hook: str = Field(
        ...,
        description=(
            "EIN Satz der neugierig macht — Spannung, Gegensatz oder "
            "offene Frage. Max ~20 Wörter. KEIN Recap der Parteipositionen, "
            "sondern ein Türöffner für das Gespräch. "
            "Beispiel: 'Hier trennt sich der Wahlkampf — soll der Staat "
            "lenken oder der Markt entscheiden?'"
        ),
    )
    suggested_question: str = Field(
        ...,
        description=(
            "Eine konkrete Frage die der Nutzer zu dieser Richtung stellen könnte. "
            "Beispiel: 'Welche konkreten Maßnahmen planen die Parteien zur Mietpreisbremse?'"
        ),
    )


class TopicScoutLLMOutput(BaseModel):
    """LLM output schema for topic scouting."""

    directions: list[LLMTopicDirection] = Field(
        ...,
        description="2-3 Themenrichtungen die der Nutzer erkunden kann",
        min_length=2,
        max_length=3,
    )
    cacheable: bool = Field(
        default=False,
        description=(
            "Setze auf true wenn die Frage ein allgemeines, breites Thema ist "
            "(z.B. 'Mieten & Wohnen', 'Klima & Energie') und die Ergebnisse "
            "für andere Nutzer wiederverwendbar wären. Setze auf false bei "
            "sehr spezifischen oder persönlichen Fragen."
        ),
    )


SYSTEM_PROMPT = """Du bist ein politischer Themen-Scout.

{party_context}

# Aufgabe
Analysiere die bereitgestellten Auszüge aus Wahlprogrammen und identifiziere
2-3 Themenrichtungen, die der Nutzer vertiefen kann. Nimm lieber WENIGE,
klar abgegrenzte Richtungen als viele schwammige — wenn die Quelltexte nur
zwei klare Cluster hergeben, gib zwei aus, nicht drei.

# Regeln
1. Jede Richtung muss durch die vorhandenen Quelltexte abgedeckt sein
2. Richtungen sollen sich klar voneinander unterscheiden
3. Namen müssen konkret und verständlich sein (NICHT "Sonstiges" oder "Allgemeines")
4. Der Hook ist EIN einladender Satz — kein Inhaltsdump, sondern ein
   Türöffner. Er macht neugierig auf das Gespräch, nennt keine konkreten
   Parteinamen und keine Zahlen. Max ~20 Wörter.
5. Schreibe auf Deutsch mit korrekten Umlauten (ä, ö, ü, ß)
6. Setze das Feld 'cacheable' auf true wenn die Anfrage ein allgemeines Thema ist

# Beispiel für gute Richtungen
Frage: "Wie stehen die Parteien zur Wohnungspolitik?"
- Name: "Mietpreisbremse und Mieterschutz"
  Hook: "Soll der Staat in den Wohnungsmarkt eingreifen — oder macht das alles nur schlimmer?"
- Name: "Sozialer Wohnungsbau"
  Hook: "Wer zahlt eigentlich, wenn der Staat Millionen neuer Wohnungen bauen soll?"
- Name: "Wohneigentum fördern"
  Hook: "Eigene Wohnung als Altersvorsorge — oder Privileg, das Ungleichheit zementiert?\""""

USER_PROMPT = """Frage des Nutzers: {query}

== Auszüge aus den Wahlprogrammen ==
{rag_chunks}

== Aufgabe ==
Identifiziere 2-3 konkrete Themenrichtungen die der Nutzer basierend auf
diesen Quelltexten erkunden kann. Jede Richtung muss durch die Quelltexte
abgedeckt sein. Wenn nur zwei Richtungen wirklich gut belegt sind, gib zwei aus."""
