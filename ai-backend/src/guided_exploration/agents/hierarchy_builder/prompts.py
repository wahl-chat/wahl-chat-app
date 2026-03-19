# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Prompt templates for hierarchy builder agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.claim import Claim


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
    claim_indices: list[int] = Field(
        default_factory=list,
        description=(
            "NUR fuer Blaetter: Indizes der zugeordneten Claims aus der Eingabeliste "
            "(0-basiert). Branch-Knoten haben KEINE claim_indices."
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
Organisiere die konkreten Parteipositionen (Claims) in eine navigierbare \
Baumstruktur fuer blinde und sehbehinderte Nutzer.

# KERNPRINZIP: Bottom-Up-Struktur
Die Baumstruktur entsteht AUS den Claims — nicht umgekehrt.
Schau dir ZUERST die Claims an, dann organisiere sie in eine sinnvolle Hierarchie.

# Strukturregeln

## 1. Adaptive Zerlegung
Waehle die Zerlegungsart die am besten zum Inhalt passt:
- **Thematisch**: Energie, Verkehr, Gebaeude (wenn Claims natuerlich in Unterbereiche fallen)
- **Nach Politiktyp**: Ziele, Massnahmen, Finanzierung (wenn Claims verschiedene Dimensionen abdecken)
- **Hybrid**: Mischung aus beidem (oft am besten)

## 2. Tiefe: 2-3 Ebenen
- Ebene 1: Hauptbereiche (2-5 Knoten)
- Ebene 2: Unterbereiche (2-5 pro Hauptbereich)
- Ebene 3: Nur wenn noetig (bei sehr detailreichen Bereichen)
- Tiefe darf variieren: Ein Hauptbereich kann 3 Ebenen haben, ein anderer nur 2

## 3. Blaetter = Vergleichspunkte
Jeder Blattknoten ist ein Vergleichspunkt, an dem Parteipositionen verglichen werden.
- Mindestens 2 Parteien pro Blatt (idealerweise mehr)
- Wenn eine Partei KEINE Position hat, ist das ebenfalls informativ
- Jeder Claim muss GENAU EINEM Blatt zugeordnet werden

## 4. KEINE leeren Blaetter
Jedes Blatt MUSS mindestens 2 Claims von mindestens 2 verschiedenen Parteien haben.
Claims die nicht gut passen: in ein breiteres Blatt einordnen, nicht weglassen.

## 5. Beschreibende Namen (Barrierefreiheit!)
Ein Screenreader-Nutzer navigiert den Baum nur ueber die Namen.
- FALSCH: "Sonstiges", "Weiteres", "Massnahmen"
- RICHTIG: "Erneuerbare Energien und Ausbau", "CO2-Bepreisung und Emissionshandel"

## 6. claim_indices NUR bei Blaettern
- Branch-Knoten (mit children): claim_indices = [] (leer!)
- Blatt-Knoten (ohne children): claim_indices = [0, 3, 7, ...] (zugeordnete Claims)

# Qualitaetspruefung
Bevor du antwortest, pruefe:
1. Hat jeder Blattknoten Claims von mindestens 2 Parteien?
2. Sind die Namen fuer Screenreader verstaendlich?
3. Ist die Tiefe angemessen (nicht zu flach, nicht zu tief)?
4. Sind alle Claims zugeordnet (keiner vergessen)?
5. Sind die Hauptbereiche etwa gleich gross?"""

CONSTRUCTION_PROMPT = """Organisiere diese {claim_count} Parteipositionen in einen \
navigierbaren Vergleichsbaum:

Benutzeranfrage: {query}

# Claims (Index: [Partei] Aussage)
{formatted_claims}

# Aufgabe
1. Lies ALLE Claims durch
2. Finde natuerliche Gruppierungen (thematisch, nach Politiktyp, oder hybrid)
3. Baue eine 2-3-stufige Hierarchie
4. Ordne JEDEN Claim genau einem Blattknoten zu (ueber claim_indices, 0-basiert)

Wichtig:
- Jeder Blattknoten braucht Claims von mindestens 2 Parteien
- Alle Claims muessen zugeordnet werden
- Namen muessen fuer Screenreader eigenstaendig verstaendlich sein"""


def format_claims_for_prompt(
    claims: list[Claim],
    parties: dict[str, PartyInfo],
) -> str:
    """Format all claims for the hierarchy builder prompt."""
    if not claims:
        return "Keine Claims verfuegbar."

    lines = []
    for i, claim in enumerate(claims):
        party_name = parties.get(
            claim.party_id,
            PartyInfo(
                party_id=claim.party_id,
                name=claim.party_id.upper(),
                long_name=claim.party_id.upper(),
                description=None,
            ),
        ).name
        lines.append(f"[{i}] [{party_name}] ({claim.claim_type}) {claim.content}")

    return "\n".join(lines)
