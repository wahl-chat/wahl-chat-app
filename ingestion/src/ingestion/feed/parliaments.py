# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The parliaments the digest covers, and how their parties are displayed."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from ingestion.connectors.manifesto_uploads.election_fixtures import fixture_dir

logger = logging.getLogger(__name__)

ParliamentId = Literal["bundestag", "landtag_st", "landtag_bw"]

# Same switch as the manifesto uploads: the seed files are not in the job
# image, so a deployed job reads the parties from the live database.
_SOURCE_ENV = "ELECTION_FIXTURES_SOURCE"

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
    # Built by default. The Landtage are not: abgeordnetenwatch publishes
    # their votes one to five months late, so an edition built two weeks
    # after the sitting would be missing most of them.
    in_feed: bool = True


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
        in_feed=False,
    ),
    "landtag_bw": Parliament(
        id="landtag_bw",
        name="Landtag Baden-Württemberg",
        region="DE-BW",
        party_context_id="landtagswahl-baden-wuerttemberg-2026",
        has_speeches=False,
        in_feed=False,
    ),
}

# What a run builds without an explicit --parliament.
FEED_PARLIAMENTS: list[str] = sorted(p.id for p in PARLIAMENTS.values() if p.in_feed)


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


def _seed_party_rows(
    parliament: Parliament, env: str, data_dir: Optional[Path]
) -> list[dict]:
    folder = data_dir / env if data_dir is not None else fixture_dir(env)
    path = folder / f"parties_{parliament.party_context_id}.json"
    try:
        return _party_rows(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        logger.warning("No party seed for %s (%s): %s", parliament.id, path, exc)
        return []


def _firestore_party_rows(parliament: Parliament) -> list[dict]:
    from ingestion.firestore_client import firestore_client  # noqa: PLC0415

    context = parliament.party_context_id
    try:
        docs = (
            firestore_client()
            .collection("contexts")
            .document(context)
            .collection("parties")
            .stream()
        )
        return [{"party_id": doc.id, **(doc.to_dict() or {})} for doc in docs]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "No parties in Firestore for %s (%s): %s", parliament.id, context, exc
        )
        return []


def load_party_display(
    parliament: Parliament, env: str, data_dir: Optional[Path] = None
) -> dict[str, PartyDisplay]:
    """Display name + colour per party slug, from the context's parties.

    A missing source only costs colours and long names (the fallbacks below),
    never the run.
    """
    source = (os.getenv(_SOURCE_ENV) or "files").strip().lower()
    if source == "firestore":
        rows = _firestore_party_rows(parliament)
    else:
        rows = _seed_party_rows(parliament, env, data_dir)
    display: dict[str, PartyDisplay] = {}
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
