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
        description=(
            "Eindeutige ID, z.B. 'erneuerbare-energien'. "
            "Dotted IDs sind nicht noetig — Tiefe wird ueber `children` ausgedrueckt, "
            "nicht ueber Namensschemata."
        ),
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
            "Top-Level-Knoten des Baums. Default ist flach: die Top-Level-Knoten "
            "SIND die Blaetter. Nur wenn eine Gruppe von Positionen wirklich in "
            "klar unterscheidbare Cluster zerfaellt, darf ein Top-Level-Knoten "
            "children haben. Mischungen aus Blatt- und Branch-Knoten auf "
            "Top-Level sind explizit erlaubt und oft die beste Wahl."
        ),
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Strukturierungsagent fuer politische Positionsvergleiche.

# Kontext
Wahlkontext: {context_name}

{party_context}

{study_mode_block}

# Aufgabe
Organisiere die konkreten Parteipositionen in eine navigierbare \
Baumstruktur fuer blinde und sehbehinderte Nutzer.

# KERNPRINZIP: Bottom-Up-Struktur
Die Baumstruktur entsteht AUS den Positionen — nicht umgekehrt.
Schau dir ZUERST die Positionen an, dann organisiere sie in eine sinnvolle Hierarchie.

# Strukturregeln

## 1. Flach ist der Default
- Starte IMMER mit einer flachen Liste von Blattknoten auf Top-Level.
- Jeder Top-Level-Knoten ist ein Gespraechseinstieg (Blatt) — kein Ordner
  mit Unterthemen.
- Gruppiere nur dann in Unterknoten, wenn die Positionen in EINEM Blatt
  aus Nutzersicht zu heterogen waeren, um ein fokussiertes Gespraech zu
  fuehren (z.B. "Klima" waere zu gross, aber "CO2-Preis" und "Verkehr"
  sind natuerliche separate Blaetter — also zwei Top-Level-Blaetter,
  keine Klima-Mutter mit zwei Kindern).
- Mischungen sind explizit erlaubt: ein Baum kann 3 Blaetter auf
  Top-Level haben und ein Thema davon noch einmal in 2 Unter-Blaetter
  aufteilen. Symmetrie ist KEIN Qualitaetsmerkmal.

## 2. Tiefe: adaptiv (1-3 Ebenen)
- Default-Tiefe = 1 Ebene (nur Blaetter).
- Tiefe > 1 nur wenn eine sinnvolle Teilung nicht anders geht.
- Erzwinge keine kuenstliche Tiefe — "Klima und Energie" als Branch mit
  zwei Kindern ist fast immer schlechter als zwei Top-Level-Blaetter.

## 3. Blaetter = Gespraechseinstiege
Jeder Blattknoten ist ein Einstiegspunkt fuer ein Gespraech, kein Fakten-Dump.
- Positionen von MINDESTENS 2 Parteien pro Blatt (idealerweise alle).
- Jede Position gehoert zu GENAU EINEM Blatt.
- Kleine Datasets (z.B. 2-3 Positionen pro Blatt) sind voellig in Ordnung,
  solange das Blatt zwei Parteien vergleicht.
- Ein einzelnes Blatt mit allen Positionen eines Subthemas ist akzeptabel.

## 4. Namen: kurz, konkret, eigenstaendig verstaendlich
- Maximal 2-4 Woerter pro Name.
- Konkret genug, dass ein Screenreader-Nutzer ohne Kontext weiss, worum es geht.
- KEINE Koordinationsformulierungen wie "X und Y" — das sind zwei Themen, mach zwei Blaetter.
- FALSCH: "Sonstiges", "Weiteres", "Klima und Energie", "Soziale Gerechtigkeit und Arbeit"
- RICHTIG: "CO2-Preis", "Erneuerbare Energien", "Bürgergeld", "Rente"

## 5. position_indices NUR bei Blaettern
- Branch-Knoten (mit children): position_indices = [] (leer!)
- Blatt-Knoten (ohne children): position_indices = [0, 3, 7, ...] (zugeordnete Positionen)

# Qualitaetspruefung
Bevor du antwortest, pruefe:
1. Hat jeder Blattknoten Positionen von mindestens 2 Parteien?
2. Sind die Namen fuer Screenreader verstaendlich?
3. Sind alle Positionen zugeordnet (keine vergessen)?
4. Wuerde die Struktur auch ganz flach gut funktionieren? Wenn ja, MACH sie flach.
5. Hat jeder Branch-Knoten mindestens 2 Kinder? Einkindige Branches
   sind immer falsch — mach das Kind zum Top-Level-Blatt stattdessen."""

STUDY_MODE_BLOCK = """# STUDIEN-MODUS (HARTE REGEL — UEBERSCHREIBT ALLES ANDERE)
Dies ist eine Nutzerstudie mit 10 Minuten Zeitbudget.

- Gib GENAU 2 oder 3 Top-Level-Knoten zurueck. Keine weniger, keine mehr.
- ALLE Top-Level-Knoten muessen BLAETTER sein. `children` ist IMMER leer.
- KEINE Verschachtelung. KEINE Branch-Knoten. KEINE Ebenen tiefer als 1.
- Jeder Blattknoten braucht Positionen von mindestens 2 Parteien.
- Verteile ALLE Positionen auf die 2-3 Blaetter.
- Waehle die 2-3 Themen, die sich am staerksten zwischen den Parteien unterscheiden
  und echten Vergleich erlauben.
"""

STUDY_MODE_BLOCK_EMPTY = ""


CONSTRUCTION_PROMPT = """Organisiere diese {position_count} Parteipositionen in einen \
navigierbaren Vergleichsbaum:

Benutzeranfrage: {query}

# Positionen (Index: [Partei] Aussage)
{formatted_positions}

# Aufgabe
1. Lies ALLE Positionen durch
2. Finde natuerliche Gespraechseinstiege (Blaetter) — jedes Blatt ist ein
   fokussiertes Thema, an dem sich Parteien vergleichen lassen
3. Default: alle Blaetter auf Top-Level (flache Liste). Baue Unterknoten
   nur, wenn ein Blatt sonst zu heterogen waere.
4. Ordne JEDE Position genau einem Blattknoten zu (ueber position_indices, 0-basiert)

Wichtig:
- Jeder Blattknoten braucht Positionen von mindestens 2 Parteien
- Keine einkindigen Branches — dann lieber direkt als Top-Level-Blatt
- Mischbaum ist OK: manche Top-Level-Knoten koennen Blaetter sein,
  andere Branches mit eigenen Kindern
- Alle Positionen muessen zugeordnet werden
- Namen muessen fuer Screenreader eigenstaendig verstaendlich sein

{study_mode_reminder}"""

STUDY_MODE_REMINDER = (
    "STUDIEN-MODUS AKTIV: Gib GENAU 2 oder 3 Top-Level-BLAETTER zurueck. "
    "Keine Verschachtelung. Keine Branches. `children` bleibt leer. "
    "Verteile alle Positionen auf diese 2-3 Blaetter."
)
STUDY_MODE_REMINDER_EMPTY = ""


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
