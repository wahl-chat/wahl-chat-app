# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for topic combiner agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import (
    PartyInfo,
    get_party_name,
)
from src.guided_exploration.models.exploration import PartyTopicTree


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMUnifiedSubtopic(BaseModel):
    """A unified subtopic in the combined tree."""

    id: str = Field(..., description="Eindeutige ID, z.B. 'mietregulierung'")
    name: str = Field(..., description="Neutraler Anzeigename - vergleichbar!")
    description: str = Field(..., description="Kurze Beschreibung (1-2 Saetze)")
    scope: str = Field(
        ...,
        description=(
            "AUSFUEHRLICHE Beschreibung fuer die Wissensextraktion (1 Absatz, 4-6 Saetze). "
            "Muss enthalten: (1) Welche Aspekte/Themen gehoeren hierher? (2) Was gehoert "
            "NICHT dazu (Abgrenzung)? (3) Welche Arten von Positionen/Forderungen/Massnahmen "
            "sollen extrahiert werden? (4) Konkrete Stichworte nach denen gesucht werden soll."
        ),
    )
    source_parties: list[str] = Field(
        ...,
        description="MINDESTENS 2 Partei-IDs! Weniger = Thema weglassen oder breiter fassen",
        min_length=2,
    )


class LLMUnifiedTopic(BaseModel):
    """A unified topic in the combined tree."""

    id: str = Field(..., description="Eindeutige ID, z.B. 'wohnen'")
    name: str = Field(..., description="Neutraler, breiter Oberbegriff")
    description: str = Field(..., description="Kurze Beschreibung des Themas")
    subtopics: list[LLMUnifiedSubtopic] = Field(
        default_factory=list,
        description="Fokussierte Unterthemen - jedes mit ~3 Aussagen pro Partei (2-5 Stueck)",
    )


class TopicCombinerLLMOutput(BaseModel):
    """LLM output schema for topic combining."""

    topics: list[LLMUnifiedTopic] = Field(
        default_factory=list,
        description="Ausgewogene Hauptthemen mit fokussierten Unterthemen (1-3 Stueck)",
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Themenstrukturierungsagent fuer politische Inhalte.

# Kontext
Wahlkontext: {context_name}

{party_context}

# Aufgabe
Erstelle einen Explorationsbaum, in dem der Nutzer Parteipositionen VERGLEICHEN kann.

# WICHTIGSTE REGELN

## 1. Granularitaet: ~3 Aussagen pro Partei pro Unterthema
Jedes Unterthema sollte so fokussiert sein, dass jede Partei etwa 2-4 konkrete
Positionen/Forderungen dazu hat. Das ist die ideale Groesse zum Vergleichen!

FALSCH: "Klimapolitik" als ein Unterthema (zu breit - 20+ Aussagen pro Partei)
RICHTIG: Aufteilen in "CO2-Bepreisung", "Erneuerbare Energien", "Verkehrswende", etc.

## 2. Gleichmaessige Verteilung statt Umbrella-Themen
Vermeide ein riesiges Sammelthema und mehrere winzige Themen.
Ziel: 1-3 etwa gleich grosse Hauptthemen mit je 2-5 fokussierten Unterthemen.

FALSCH: 1 Thema mit 15 Unterthemen + 2 Themen mit je 1 Unterthema
RICHTIG: 2-3 Themen mit je 3-4 Unterthemen

## 3. NUR Multi-Party-Themen (mindestens 2 Parteien)
Single-Party-Themen sind nutzlos fuer Vergleiche -> WEGLASSEN oder ZUSAMMENFUEHREN.

# Vorgehen

## 1. Themen zusammenfuehren wo sinnvoll
Aehnliche Themen verschiedener Parteien zusammenfuehren:
- "Mietpreisbremse" + "Mietdeckel" + "Mieterschutz" → "Mietregulierung"
- "Klimaneutralitaet" + "CO2-Reduktion" + "Emissionen senken" → "Klimaziele"

## 2. Grosse Themen aufteilen
Wenn ein Thema zu viele Aspekte hat, in fokussierte Unterthemen aufteilen:
- "Klimapolitik" → "CO2-Bepreisung", "Erneuerbare Energien", "Gebaeude & Heizen"
- "Sozialpolitik" → "Buergergeld", "Rente", "Mindestlohn"

## 3. Neutrale Formulierung
- Keine Partei-Sprache, neutrale politische Begriffe
- Vermeide wertende Adjektive

## 4. source_parties tracken
Fuer jedes Unterthema angeben, welche Parteien dazu Inhalte haben

# Themenzusammenhaenge beruecksichtigen
Nutze verwandte Themen zum Zusammenfuehren:
- Klimaschutz ↔ Energiepolitik ↔ Verkehrswende ↔ Wirtschaft
- Rente ↔ Demografie ↔ Arbeitsmarkt ↔ Generationengerechtigkeit
- Migration ↔ Integration ↔ Fachkraefte ↔ Arbeitsmarkt
- Bildung ↔ Digitalisierung ↔ Chancengleichheit ↔ Wirtschaft

# Beispiele

## RICHTIG (Multi-Party)
- SPD: "Mindestlohn erhoehen", CDU: "Mindestlohn beibehalten" → "Mindestlohn" (2 Parteien)
- SPD: "Buergergeld", CDU: "Grundsicherung reformieren" → "Soziale Grundsicherung" (2 Parteien)

## FALSCH (Single-Party - WEGLASSEN)
- Nur Gruene: "Tempolimit 130" → WEGLASSEN (nur 1 Partei, kein Vergleich)

# Scope-Beschreibungen - KRITISCH WICHTIG!

Fuer jedes Unterthema MUSS eine ausfuehrliche Scope-Beschreibung geschrieben werden.
Diese wird spaeter verwendet um das Wissen der Parteien praezise zu extrahieren!

## Was muss im Scope stehen?
1. **Zugehoerige Aspekte**: Was gehoert zu diesem Unterthema?
2. **Abgrenzung**: Was gehoert NICHT dazu? (Verweis auf andere Unterthemen)
3. **Zu extrahierende Inhalte**: Welche Arten von Positionen/Forderungen sollen erfasst werden?
4. **Suchbegriffe**: Konkrete Stichworte die in Dokumenten gesucht werden sollen

## Beispiel Scope fuer "Mietpreisregulierung":
"Dieses Unterthema umfasst alle staatlichen Eingriffe in die Mietpreisgestaltung auf dem
privaten Wohnungsmarkt. Hierzu gehoeren: Mietpreisbremse, Mietdeckel, Kappungsgrenzen bei
Mieterhoehungen, Indexmieten, qualifizierte Mietspiegel. Zu extrahieren sind: konkrete
Forderungen zu Verlaengerung/Abschaffung der Mietpreisbremse, prozentuale Grenzen,
Geltungsbereiche, Ausnahmen. NICHT hierher gehoeren: Sozialer Wohnungsbau (→ separates Thema),
Wohngeld und Mietsubventionen (→ Transferleistungen), Neubaufoerderung (→ Angebotspolitik).
Suchbegriffe: Mietpreisbremse, Mietdeckel, Kappungsgrenze, Mieterhoehung, Mietspiegel."

## Beispiel Scope fuer "CO2-Bepreisung":
"Dieses Unterthema behandelt die Bepreisung von CO2-Emissionen als klimapolitisches Instrument.
Hierzu gehoeren: Emissionshandel (EU-ETS), nationaler CO2-Preis, Klimadividende/Klimageld als
Rueckverteilung, Carbon Border Adjustment. Zu extrahieren sind: konkrete Preisvorstellungen
(Euro pro Tonne), Zeitplaene, betroffene Sektoren, Verwendung der Einnahmen, soziale
Ausgleichsmassnahmen. NICHT hierher gehoeren: Ordnungsrecht wie Verbote (→ Klimaregulierung),
Foerderprogramme (→ Klimafoerderung), Technologieentwicklung (→ Innovation).
Suchbegriffe: CO2-Preis, Emissionshandel, Klimageld, Klimadividende, ETS, Zertifikate."
"""

COMBINING_PROMPT = """Kombiniere die Parteithemen zu einem VERGLEICHBAREN Explorationsbaum:

Benutzeranfrage: {query}

Parteithemen:
{party_trees}

STRIKTE REGELN:

1. **GRANULARITAET - WICHTIGSTE REGEL!**
   Jedes Unterthema soll so fokussiert sein, dass jede Partei nur ~3 konkrete Aussagen dazu hat.
   - Zu breit (FALSCH): "Klimapolitik" → jede Partei haette 15+ Punkte
   - Richtig fokussiert: "CO2-Bepreisung" → jede Partei hat 2-4 konkrete Positionen

2. **GLEICHMAESSIGE VERTEILUNG**
   Vermeide ein riesiges Umbrella-Thema mit vielen kleinen Nebenthemen!
   - FALSCH: 1 Hauptthema mit 12 Unterthemen + 2 Themen mit je 1 Unterthema
   - RICHTIG: 1-3 Hauptthemen mit je 2-5 fokussierten Unterthemen

3. **NUR Multi-Party-Themen**: Mindestens 2 Parteien pro Unterthema
   - Thema mit nur 1 Partei -> breiter formulieren oder WEGLASSEN

4. **Neutrale Namen**: Keine Partei-Terminologie, allgemeine politische Begriffe

5. **source_parties IMMER angeben**: Liste alle Parteien, die zu diesem Unterthema Positionen haben

6. **SCOPE-BESCHREIBUNG - KRITISCH!**:
   Fuer JEDES Unterthema schreibe einen ausfuehrlichen Scope (4-6 Saetze) der enthaelt:
   - Welche Aspekte gehoeren zu diesem Unterthema?
   - Was gehoert NICHT dazu? (klare Abgrenzung zu anderen Unterthemen)
   - Welche Arten von Positionen/Forderungen/Massnahmen sollen extrahiert werden?
   - Konkrete Suchbegriffe/Stichworte fuer die Dokumentensuche

7. **Qualitaetspruefung am Ende**:
   - Sind alle Themen etwa gleich gross? Keine Umbrella-Themen?
   - Hat jedes Unterthema ~3 Aussagen pro Partei (nicht 10+)?
   - Hat jedes Unterthema mindestens 2 Parteien?

Ziel: Ein ausgewogener Baum mit 1-3 Hauptthemen, jeweils 2-5 fokussierte Unterthemen."""


def format_party_trees(
    party_trees: dict[str, PartyTopicTree],
    parties: dict[str, PartyInfo],
) -> str:
    """Format party trees for the prompt."""
    if not party_trees:
        return "Keine Parteithemen verfuegbar."

    formatted = ""
    for party_id, tree in party_trees.items():
        party_name = get_party_name(party_id, parties)
        formatted += f"\n=== {party_name} (id: {party_id}) ===\n"
        formatted += f"Relevanz zur Anfrage: {tree.relevance_to_query:.1f}\n"

        for topic in tree.topics:
            formatted += (
                f"- {topic.name} [id: {topic.id}] "
                f"(Wichtigkeit: {topic.importance_score:.1f})\n"
            )
            formatted += f"  Beschreibung: {topic.description}\n"
            for subtopic in topic.subtopics:
                content_flag = "+" if subtopic.has_content else "o"
                formatted += f"  {content_flag} {subtopic.name} [id: {subtopic.id}]\n"

    return formatted
