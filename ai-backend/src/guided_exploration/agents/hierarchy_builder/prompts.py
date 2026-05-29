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
            "Dotted IDs sind nicht nötig — Tiefe wird über `children` ausgedrückt, "
            "nicht über Namensschemata."
        ),
    )
    name: str = Field(
        ...,
        description=(
            "Beschreibender Anzeigename. Muss für Screenreader-Nutzer "
            "eigenständig verständlich sein."
        ),
    )
    description: str = Field(
        ...,
        description="Kurze Beschreibung was dieser Knoten umfasst (1-2 Sätze)",
    )
    children: list["LLMHierarchyNode"] = Field(
        default_factory=list,
        description="Unterknoten. Leere Liste = Blattknoten.",
    )
    position_indices: list[int] = Field(
        default_factory=list,
        description=(
            "NUR für Blätter: Indizes der zugeordneten Positionen aus der Eingabeliste "
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
            "Top-Level-Knoten des Baums. Wenn klar unterscheidbare Cluster zerfällt, darf ein Top-Level-Knoten "
            "children haben. Mischungen aus Blatt- und Branch-Knoten auf "
            "Top-Level sind explizit erlaubt und oft die beste Wahl."
        ),
    )


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """Du bist ein Strukturierungsagent für politische Positionsvergleiche.

# Kontext
Wahlkontext: {context_name}

{party_context}

{study_mode_block}

# Aufgabe
Organisiere die konkreten Parteipositionen in eine navigierbare \
Baumstruktur für blinde und sehbehinderte Nutzer.

# KERNPRINZIP: Bottom-Up-Struktur
Die Baumstruktur entsteht AUS den Positionen — nicht umgekehrt.
Schau dir ZUERST die Positionen an, dann organisiere sie in eine sinnvolle Hierarchie.

# Strukturregeln

## 1. Erst Blätter finden, dann gruppieren
- Identifiziere ZUERST die Gesprächseinstiege (Blätter) bottom-up aus den Positionen.
- Gruppiere danach inhaltlich verwandte Blätter unter thematischen Top-Level-Branches.
- Jeder Blattknoten ist ein Gesprächseinstieg — kein Ordner mit Unterthemen.

## 2. Tiefe: 2 Ebenen sind der Normalfall bei vielen Themen
- Bei vielen Blättern ist eine zweistufige Struktur (Thema → Blätter) der Regelfall,
  nicht die Ausnahme.
- 1-3 Ebenen sind erlaubt; erzwinge aber keine Tiefe, wenn nur wenige Blätter existieren.

## 3. Top-Level: 3-6 Knoten
- Strebe 3-6 Top-Level-Knoten an.
- Bei mehr als ~6 Blättern MUSST du sie unter thematischen Branches gruppieren —
  eine flache Liste aus 10+ Top-Level-Blättern ist falsch.
- Eine flache Top-Level-Liste ist nur akzeptabel, wenn es insgesamt ≤ ~6 Blätter gibt.

## 4. Blätter = Gesprächseinstiege
Jeder Blattknoten ist ein Einstiegspunkt für ein Gespräch, kein Fakten-Dump.
- Positionen von MINDESTENS 2 Parteien pro Blatt (idealerweise alle).
- Jede Position gehört zu GENAU EINEM Blatt.
- Kleine Datasets (z.B. 2-3 Positionen pro Blatt) sind völlig in Ordnung,
  solange das Blatt zwei Parteien vergleicht.
- Ein einzelnes Blatt mit allen Positionen eines Subthemas ist akzeptabel.

## 5. Namen: kurz, konkret, eigenständig verständlich
- Maximal 2-4 Wörter pro Name.
- Konkret genug, dass ein Screenreader-Nutzer ohne Kontext weiß, worum es geht.
- KEINE Koordinationsformulierungen wie "X und Y" — das sind zwei Themen, mach zwei Blätter.
  Wenn beide thematisch zusammengehören, hänge sie als zwei Blätter unter einen
  gemeinsamen Branch (z.B. Branch "Klima" mit Blättern "CO2-Preis" und "Erneuerbare Energien").
- FALSCH: "Sonstiges", "Weiteres", "Klima und Energie", "Soziale Gerechtigkeit und Arbeit"
- RICHTIG: "CO2-Preis", "Erneuerbare Energien", "Bürgergeld", "Rente"

## 6. position_indices NUR bei Blättern
- Branch-Knoten (mit children): position_indices = [] (leer!)
- Blatt-Knoten (ohne children): position_indices = [0, 3, 7, ...] (zugeordnete Positionen)

# Qualitätsprüfung
Bevor du antwortest, prüfe:
1. Hast du mehr als ~6 Top-Level-Knoten? Dann gruppiere verwandte Blätter
   unter thematischen Branches.
2. Hat jeder Blattknoten Positionen von mindestens 2 Parteien?
3. Sind die Namen für Screenreader verständlich?
4. Sind alle Positionen zugeordnet (keine vergessen)?
5. Hat jeder Branch-Knoten mindestens 2 Kinder? Einkindige Branches
   sind immer falsch — mach das Kind zum Top-Level-Blatt stattdessen."""

STUDY_MODE_BLOCK = """# STUDIEN-MODUS (HARTE REGEL — UEBERSCHREIBT ALLES ANDERE)
Dies ist eine Nutzerstudie. Die Blätter werden parallel vor-generiert,
die Anzahl beeinflusst die Wartezeit nicht.

- Gib HOECHSTENS 4 Top-Level-Knoten zurück. Wähle die Anzahl so, wie es
  das Material hergibt — wenn die Positionen natürlich in zwei klar
  unterscheidbare Cluster fallen, gib zwei zurück; wenn vier saubere
  Sub-Aspekte sichtbar sind, gib vier zurück. Erfinde keine künstliche
  Aufspaltung, nur um die Obergrenze auszuschöpfen.
- Ein Blatt sollte einen klar abgegrenzten Sub-Aspekt abdecken
  (z.B. getrennt: "Tempolimit", "Verbrennerverbot", "ÖPNV-Ausbau"),
  nicht ein ganzes Politikfeld zusammenfassen.
- ALLE Top-Level-Knoten müssen BLAETTER sein. `children` ist IMMER leer.
- KEINE Verschachtelung. KEINE Branch-Knoten. KEINE Ebenen tiefer als 1.
- Jeder Blattknoten braucht Positionen von mindestens 2 Parteien.
  Reine Single-Party-Blätter sind verboten.
- Verteile ALLE Positionen auf die Blätter. Keine darf wegfallen.

## Auffang-Blatt für Übrig-Positionen
Wenn nach 3 fokussierten Sub-Aspekten Positionen übrig bleiben, die
keinem davon sauber zuzuordnen sind, sammle sie in EINEM zusätzlichen
Blatt — das wird das 4. (und letzte) Top-Level-Blatt.

Anforderungen:
- Das Blatt braucht eine **innere thematische Klammer** — irgendetwas
  verbindet die übrigen Positionen inhaltlich (z.B. „Internationale
  Klima-Kooperation", „Klimaanpassung statt Vermeidung", „Klima und
  Wirtschaftsstandort"). Keine reine Resterampe ohne roten Faden.
- Wenn die Klammer klar erkennbar ist, **benenne das Blatt nach der
  Klammer** — das ist immer besser. Nimm den Namen „Sonstiges" oder
  „Weiteres" nur, wenn wirklich keine engere Klammer beschreibbar ist;
  in der `description` muss dann der rote Faden trotzdem benannt sein.
- Es gelten weiterhin: ≥ 2 Parteien, Blatt (kein Branch), Positionen
  NUR über `position_indices`.
- Wenn nichts übrig bleibt, dieses Blatt einfach weglassen — es ist
  kein Pflicht-Slot, nur eine zulässige Auffang-Option.
"""

STUDY_MODE_BLOCK_EMPTY = ""


CONSTRUCTION_PROMPT = """Organisiere diese {position_count} Parteipositionen in einen \
navigierbaren Vergleichsbaum:

Benutzeranfrage: {query}

# Positionen (Index: [Partei] Aussage)
{formatted_positions}

# Aufgabe
1. Lies ALLE Positionen durch
2. Finde natürliche Gesprächseinstiege (Blätter) — jedes Blatt ist ein
   fokussiertes Thema, an dem sich Parteien vergleichen lassen
3. Gruppiere verwandte Blätter unter thematischen Top-Level-Branches
   (Ziel: 3-6 Top-Level-Knoten). Eine flache Top-Level-Liste ist nur OK,
   wenn es insgesamt ≤ ~6 Blätter gibt.
4. Ordne JEDE Position genau einem Blattknoten zu (über position_indices, 0-basiert)

Wichtig:
- Jeder Blattknoten braucht Positionen von mindestens 2 Parteien
- Keine einkindigen Branches — dann lieber direkt als Top-Level-Blatt
- Mischbaum ist OK: manche Top-Level-Knoten können Blätter sein,
  andere Branches mit eigenen Kindern
- Alle Positionen müssen zugeordnet werden
- Namen müssen für Screenreader eigenständig verständlich sein

{study_mode_reminder}"""

STUDY_MODE_REMINDER = (
    "STUDIEN-MODUS AKTIV: Gib HOECHSTENS 4 Top-Level-BLAETTER zurück. "
    "Anzahl richtet sich nach den natürlichen Sub-Aspekten im Material — "
    "nicht künstlich aufspalten, um die Obergrenze zu erreichen. "
    "Keine Verschachtelung. Keine Branches. `children` bleibt leer. "
    "Verteile alle Positionen; jedes Blatt braucht mindestens 2 Parteien. "
    "Wenn nach 3 fokussierten Sub-Aspekten Positionen übrig bleiben, "
    "fasse sie zu EINEM 4. Auffang-Blatt zusammen — bevorzugt benannt "
    "nach der inneren thematischen Klammer (z.B. \"Internationale "
    "Klima-Kooperation\"), nur als letzte Wahl \"Sonstiges\". "
    "Wenn nichts übrig bleibt, das Auffang-Blatt weglassen."
)
STUDY_MODE_REMINDER_EMPTY = ""


def format_positions_for_prompt(
    positions: list[Position],
    parties: dict[str, PartyInfo],
) -> str:
    """Format all positions for the hierarchy builder prompt."""
    if not positions:
        return "Keine Positionen verfügbar."

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
