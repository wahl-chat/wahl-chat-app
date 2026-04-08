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
    description: str = Field(
        ...,
        description="1-2 Sätze die beschreiben, worum es in dieser Richtung geht",
    )
    party_stances_preview: str = Field(
        ...,
        description=(
            "Kurze Zusammenfassung (1-2 Sätze) wie die Parteien in dieser "
            "Richtung tendieren — z.B. welche Parteien dafür/dagegen sind"
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
        description="3-5 Themenrichtungen die der Nutzer erkunden kann",
        min_length=2,
        max_length=6,
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
3-5 Themenrichtungen, die der Nutzer vertiefen kann.

# Regeln
1. Jede Richtung muss durch die vorhandenen Quelltexte abgedeckt sein
2. Richtungen sollen sich klar voneinander unterscheiden
3. Namen müssen konkret und verständlich sein (NICHT "Sonstiges" oder "Allgemeines")
4. Die Zusammenfassung der Parteipositionen muss neutral und faktenbasiert sein
5. Nenne in der Zusammenfassung konkrete Parteien und ihre Tendenzen
6. Bevorzuge Richtungen die für mehrere Parteien relevant sind
7. Schreibe auf Deutsch mit korrekten Umlauten (ä, ö, ü, ß)
8. Setze das Feld 'cacheable' auf true wenn die Anfrage ein allgemeines Thema ist

# Beispiel für gute Richtungen
Frage: "Wie stehen die Parteien zur Wohnungspolitik?"
- "Mietpreisbremse und Mieterschutz" — SPD und Grüne setzen auf stärkere Regulierung, FDP lehnt Eingriffe ab
- "Sozialer Wohnungsbau" — Breiter Konsens für mehr Bau, aber unterschiedliche Finanzierungsmodelle
- "Wohneigentum fördern" — CDU und FDP betonen Eigentumsbildung, Linke priorisiert Mietwohnungen"""

USER_PROMPT = """Frage des Nutzers: {query}

== Auszüge aus den Wahlprogrammen ==
{rag_chunks}

== Aufgabe ==
Identifiziere 3-5 konkrete Themenrichtungen die der Nutzer basierend auf
diesen Quelltexten erkunden kann. Jede Richtung muss durch die Quelltexte
abgedeckt sein."""
