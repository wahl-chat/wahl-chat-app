# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for hierarchy builder agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.position import Position


# =============================================================================
# LLM Output Schema
# =============================================================================


class LLMHierarchyNode(BaseModel):
    """A node in the hierarchy produced by the LLM."""

    id: str = Field(
        ...,
        description="Eindeutige ID, z.B. 'energie' oder 'energie.erneuerbare'",
    )
    name: str = Field(
        ...,
        description=(
            "Beschreibender Anzeigename. Muss fuer Screenreader-Nutzer "
            "eigenstaendig verstaendlich sein."
        ),
    )
    description: str = Field(
        ...,
        description="Kurze Beschreibung was dieser Knoten umfasst (1-2 Saetze)",
    )
    children: list["LLMHierarchyNode"] = Field(
        default_factory=list,
        description="Unterknoten. Leere Liste = Blattknoten.",
    )
    position_indices: list[int] = Field(
        default_factory=list,
        description=(
            "NUR fuer Blaetter: Indizes der zugeordneten Positionen aus der Eingabeliste "
            "(0-basiert). Branch-Knoten haben KEINE position_indices."
        ),
    )


# Allow recursive model
LLMHierarchyNode.model_rebuild()


class HierarchyBuilderLLMOutput(BaseModel):
    """LLM output schema for hierarchy construction."""

    nodes: list[LLMHierarchyNode] = Field(
        ...,
        description=(
            "Top-Level-Knoten des Baums. Typisch 2-5 Hauptbereiche, "
            "jeder mit 2-5 Unterknoten."
        ),
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Strukturierungsagent fuer politische Positionsvergleiche.

# Kontext
Wahlkontext: {context_name}

{party_context}

# Aufgabe
Organisiere die konkreten Parteipositionen in eine navigierbare \
Baumstruktur fuer blinde und sehbehinderte Nutzer.

# KERNPRINZIP: Bottom-Up-Struktur
Die Baumstruktur entsteht AUS den Positionen — nicht umgekehrt.
Schau dir ZUERST die Positionen an, dann organisiere sie in eine sinnvolle Hierarchie.

# Strukturregeln

## 1. Adaptive Zerlegung
Waehle die Zerlegungsart die am besten zum Inhalt passt:
- **Thematisch**: Energie, Verkehr, Gebaeude (wenn Positionen natuerlich in Unterbereiche fallen)
- **Nach Politiktyp**: Ziele, Massnahmen, Finanzierung (wenn Positionen verschiedene Dimensionen abdecken)
- **Hybrid**: Mischung aus beidem (oft am besten)

## 2. Tiefe: 2-3 Ebenen
- Ebene 1: Hauptbereiche (2-5 Knoten)
- Ebene 2: Unterbereiche (2-5 pro Hauptbereich)
- Ebene 3: Nur wenn noetig (bei sehr detailreichen Bereichen)
- Tiefe darf variieren: Ein Hauptbereich kann 3 Ebenen haben, ein anderer nur 2

## 3. Blaetter = BREITE Vergleichspunkte (WICHTIGSTE REGEL!)
Jeder Blattknoten muss BREIT genug sein fuer eine tiefere Exploration.
- Mindestens 4-5 Positionen pro Blatt, idealerweise mehr
- Mindestens 2 Parteien pro Blatt (idealerweise alle)
- Jede Position muss GENAU EINEM Blatt zugeordnet werden
- LIEBER weniger, breitere Blaetter als viele enge mit nur 1-2 Positionen!

FALSCH: "Klimaneutralitaet 2035" (zu eng, nur 1-2 Positionen pro Partei)
RICHTIG: "Klimaziele und Zeitplaene" (breit genug fuer 4+ Positionen pro Partei)

## 4. KEINE duennen Blaetter
Jedes Blatt MUSS mindestens 4 Positionen von mindestens 2 Parteien haben.
Wenn ein Thema zu wenig Positionen hat: mit verwandten Positionen zusammenlegen!
Positionen die nicht gut passen: in ein breiteres Blatt einordnen, nicht weglassen.

## 5. Beschreibende Namen (Barrierefreiheit!)
Ein Screenreader-Nutzer navigiert den Baum nur ueber die Namen.
- FALSCH: "Sonstiges", "Weiteres", "Massnahmen"
- RICHTIG: "Erneuerbare Energien und Ausbau", "CO2-Bepreisung und Emissionshandel"

## 6. position_indices NUR bei Blaettern
- Branch-Knoten (mit children): position_indices = [] (leer!)
- Blatt-Knoten (ohne children): position_indices = [0, 3, 7, ...] (zugeordnete Positionen)

# Qualitaetspruefung
Bevor du antwortest, pruefe:
1. Hat jeder Blattknoten mindestens 4 Positionen? Wenn nicht: zusammenlegen!
2. Hat jeder Blattknoten Positionen von mindestens 2 Parteien?
3. Sind die Namen fuer Screenreader verstaendlich?
4. Sind alle Positionen zugeordnet (keine vergessen)?
5. Wuerde ein Nutzer bei jedem Blatt genug Material fuer Folgefragen finden?"""

CONSTRUCTION_PROMPT = """Organisiere diese {position_count} Parteipositionen in einen \
navigierbaren Vergleichsbaum:

Benutzeranfrage: {query}

# Positionen (Index: [Partei] Aussage)
{formatted_positions}

# Aufgabe
1. Lies ALLE Positionen durch
2. Finde natuerliche Gruppierungen (thematisch, nach Politiktyp, oder hybrid)
3. Baue eine 2-3-stufige Hierarchie
4. Ordne JEDE Position genau einem Blattknoten zu (ueber position_indices, 0-basiert)

Wichtig:
- Jeder Blattknoten braucht MINDESTENS 4 Positionen von mindestens 2 Parteien
- Lieber wenige breite Blaetter als viele enge!
- Alle Positionen muessen zugeordnet werden
- Namen muessen fuer Screenreader eigenstaendig verstaendlich sein"""


def format_positions_for_prompt(
    positions: list[Position],
    parties: dict[str, PartyInfo],
) -> str:
    """Format all positions for the hierarchy builder prompt."""
    if not positions:
        return "Keine Positionen verfuegbar."

    lines = []
    for i, position in enumerate(positions):
        party_name = parties.get(
            position.party_id,
            PartyInfo(
                party_id=position.party_id,
                name=position.party_id.upper(),
                long_name=position.party_id.upper(),
                description=None,
            ),
        ).name
        lines.append(f"[{i}] [{party_name}] ({position.position_type}) {position.content}")

    return "\n".join(lines)
