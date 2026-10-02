# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The parliaments the digest covers, and how their parties are displayed."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

ParliamentId = Literal["bundestag", "landtag_st", "landtag_bw"]

_FIRESTORE_DATA_DIR = (
    Path(__file__).resolve().parents[3] / "firebase" / "firestore_data"
)

# Used when a party is missing from the context's seed parties (fraktionslose
# members, splinter groups, a party that left the parliament).
_FALLBACK_COLOR = "#9CA3AF"
_FALLBACK_NAMES: dict[str, str] = {
    "fraktionslos": "Fraktionslos",
    "fraktionslose": "Fraktionslos",
    "unbekannt": "Unbekannt",
}


@dataclass(frozen=True)
class Parliament:
    id: ParliamentId
    name: str
    region: str
    # The election context whose seed parties supply display names and colours.
    party_context_id: str
    # Speech chunks exist only for the Bundestag; the Landtage get votes only.
    has_speeches: bool
    # Party slugs whose display name differs in this parliament (the Union sits
    # as one Bundestag fraction that the vote connector attributes to "cdu").
    name_overrides: tuple[tuple[str, str], ...] = ()
    # Party slugs that sit in another party's Fraktion here (the CSU in the
    # Union's Bundestag Fraktion); speeches are attributed to the Fraktion.
    party_aliases: tuple[tuple[str, str], ...] = ()


PARLIAMENTS: dict[str, Parliament] = {
    "bundestag": Parliament(
        id="bundestag",
        name="Bundestag",
        region="DE",
        party_context_id="bundestagswahl-2025",
        has_speeches=True,
        name_overrides=(("cdu", "CDU/CSU"),),
        party_aliases=(("csu", "cdu"),),
    ),
    "landtag_st": Parliament(
        id="landtag_st",
        name="Landtag Sachsen-Anhalt",
        region="DE-ST",
        party_context_id="landtagswahl-sachsen-anhalt-2026",
        has_speeches=False,
    ),
    "landtag_bw": Parliament(
        id="landtag_bw",
        name="Landtag Baden-Württemberg",
        region="DE-BW",
        party_context_id="landtagswahl-baden-wuerttemberg-2026",
        has_speeches=False,
    ),
}


@dataclass(frozen=True)
class PartyDisplay:
    name: str
    color: str


def _party_rows(raw: object) -> list[dict]:
    """Seed files are either a list of party docs or a dict keyed by party id."""
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        return [
            {"party_id": key, **value}
            for key, value in raw.items()
            if isinstance(value, dict)
        ]
    return []


def load_party_display(
    parliament: Parliament, env: str, data_dir: Optional[Path] = None
) -> dict[str, PartyDisplay]:
    """Display name + colour per party slug, from the context's seed parties."""
    path = (
        (data_dir or _FIRESTORE_DATA_DIR)
        / env
        / f"parties_{parliament.party_context_id}.json"
    )
    display: dict[str, PartyDisplay] = {}
    try:
        rows = _party_rows(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        logger.warning("No party seed for %s (%s): %s", parliament.id, path, exc)
        rows = []
    for row in rows:
        party_id = row.get("party_id")
        if not party_id:
            continue
        display[str(party_id)] = PartyDisplay(
            name=str(row.get("name") or party_id),
            color=str(row.get("background_color") or _FALLBACK_COLOR),
        )
    for party_id, name in parliament.name_overrides:
        base = display.get(party_id)
        display[party_id] = PartyDisplay(
            name=name, color=base.color if base else _FALLBACK_COLOR
        )
    return display


def party_display_for(party_id: str, display: dict[str, PartyDisplay]) -> PartyDisplay:
    known = display.get(party_id)
    if known is not None:
        return known
    return PartyDisplay(
        name=_FALLBACK_NAMES.get(party_id, party_id.upper()),
        color=_FALLBACK_COLOR,
    )
