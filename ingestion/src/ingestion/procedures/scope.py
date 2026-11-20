# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Which DIP Vorgänge are procedures, and what kind each is."""

from __future__ import annotations

from wahlchat_common.procedures import ProcedureKind

# Always procedures, plenary stage or not (an Antrag may wait for months).
CORE_TYPES: frozenset[str] = frozenset(
    {
        "Gesetzgebung",
        "Antrag",
        "Entschließungsantrag BT",
        "Aktuelle Stunde",
        "Vereinbarte Debatte",
        "Regierungserklärung",
        "Befragung der Bundesregierung",
    }
)

# Never procedures: single questions, even when asked in the Fragestunde.
EXCLUDED_TYPES: frozenset[str] = frozenset({"Mündliche Frage", "Schriftliche Frage"})

_KINDS: dict[str, ProcedureKind] = {
    "Gesetzgebung": "legislation",
    "Rechtsverordnung": "legislation",
    "Rechtsverordnung (Außenwirtschaftsrecht)": "legislation",
    "Allgemeine Verwaltungsvorschrift": "legislation",
    "Verwaltungsvorschrift": "legislation",
    "Antrag": "motion",
    "Entschließungsantrag BT": "motion",
    "Selbständiger Antrag von Ländern auf Entschließung": "motion",
    "Enquete-Kommission": "motion",
    "Aktuelle Stunde": "debate",
    "Vereinbarte Debatte": "debate",
    "Regierungserklärung": "debate",
    "Befragung der Bundesregierung": "questions",
    "Große Anfrage": "questions",
    "Kleine Anfrage": "questions",
    "Bericht, Gutachten, Programm": "report",
    "EU-Vorlage": "report",
    "Unterrichtung durch das Europäische Parlament": "report",
    "Entlastung der Bundesregierung": "report",
    "Entlastung des Bundesrechnungshofes": "report",
    "Über- und außerplanmäßige Haushaltsausgaben": "report",
}


def in_scope(vorgangstyp: str, has_bt_plenary_stage: bool) -> bool:
    """Core types always; any other type once it reached the Bundestag plenary."""
    if vorgangstyp in EXCLUDED_TYPES:
        return False
    return vorgangstyp in CORE_TYPES or has_bt_plenary_stage


def kind_of(vorgangstyp: str) -> ProcedureKind:
    """Unlisted types are elections, rules of procedure and the like."""
    return _KINDS.get(vorgangstyp, "procedural")
