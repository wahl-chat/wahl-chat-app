# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The party a speech belongs to when its chunk does not know it.

The speech connectors resolve a speaker's party from the protocol's
``<fraktion>`` or the MdB-Stammdaten. Members of the government speak in
their office and carry no ``<fraktion>``, and those from outside the
Bundestag have no Stammdaten record, so their speeches arrive as
"unbekannt". Once the protocol has identified the speaker, the feed tries,
in order: the protocol's ``<fraktion>``, the Stammdaten by the protocol's
``<redner id>``, and a hand-kept list of speakers from outside the Bundestag.

A party the chunk does know is kept. Where the protocol disagrees, the
disagreement is logged, not acted on: the chunk's party is what the corpus
is filtered by, and the two must not drift apart silently.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Callable, Optional

from ingestion.connectors.bundestag_speeches.mappers.corpus import party_to_slug
from ingestion.connectors.bundestag_speeches.utils import normalize_name_for_lookup
from ingestion.feed.reader import Speech
from ingestion.party_slugs import PARTY_SLUG_QUARANTINE

logger = logging.getLogger(__name__)

ROSTER_PATH = Path(__file__).resolve().parents[3] / "data" / "government_speakers.json"

# Speakers outside any party, whom no Fraktion speaks for.
NON_PARTISAN = "parteilos"
_UNRESOLVED = frozenset({PARTY_SLUG_QUARANTINE, ""})


@dataclass(frozen=True)
class OutsideSpeaker:
    name: str
    # None when no official source names a party: the office is still known.
    party: Optional[str]
    office: str
    institution: str
    redner_ids: tuple[str, ...] = ()


class Roster:
    """The hand-kept speakers from outside the Bundestag."""

    def __init__(self, speakers: list[OutsideSpeaker]):
        self.speakers = speakers
        self._by_id = {i: s for s in speakers for i in s.redner_ids}
        self._by_name = {normalize_name_for_lookup(s.name): s for s in speakers}

    def find(self, redner_id: Optional[str], name: str) -> Optional[OutsideSpeaker]:
        if redner_id and redner_id in self._by_id:
            return self._by_id[redner_id]
        return self._by_name.get(normalize_name_for_lookup(name))


def load_roster(path: Path = ROSTER_PATH) -> Roster:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Roster(
        [
            OutsideSpeaker(
                name=row["name"],
                party=row.get("party"),
                office=row["office"],
                institution=row["institution"],
                redner_ids=tuple(row.get("redner_ids") or ()),
            )
            for row in data["speakers"]
        ]
    )


def _stammdaten_parties() -> dict[str, str]:
    """MdB ID -> party label, from the Stammdaten the speech connectors use."""
    from ingestion.connectors.bundestag_speeches.mdb import ensure_mdb_lookup
    from ingestion.feed.politician_sources import DEFAULT_MDB_PATH

    lookup = ensure_mdb_lookup(DEFAULT_MDB_PATH)
    return {
        mdb_id: record["party"]
        for mdb_id, record in lookup["by_id"].items()
        if record.get("party")
    }


class PartyResolver:
    """Fills in the party of a speech that arrived as "unbekannt"."""

    def __init__(
        self,
        roster: Optional[Roster] = None,
        stammdaten: Callable[[], dict[str, str]] = _stammdaten_parties,
    ):
        self._roster = roster
        self._load_stammdaten = stammdaten

    @cached_property
    def roster(self) -> Roster:
        return self._roster if self._roster is not None else load_roster()

    @cached_property
    def stammdaten(self) -> dict[str, str]:
        # Read only when a speech needs it: most days every party is known.
        try:
            return self._load_stammdaten()
        except Exception as exc:  # noqa: BLE001 — the roster still answers
            logger.warning("MdB-Stammdaten unavailable for party lookup: %s", exc)
            return {}

    def __call__(self, speech: Speech) -> None:
        protocol_party = _protocol_party(speech)
        if speech.party_id not in _UNRESOLVED:
            if protocol_party is not None and not _same_fraktion(
                protocol_party, speech.party_id
            ):
                logger.warning(
                    "Party of %s: corpus says %s, protocol says %s",
                    speech.speaker,
                    speech.party_id,
                    protocol_party,
                )
            return
        found = self._resolve(speech, protocol_party)
        if found is None:
            if self.roster.find(speech.mdb_id, speech.speaker) is not None:
                return  # on the roster; no official source names a party
            logger.warning(
                "No party for %s (redner id %s); add them to %s",
                speech.speaker,
                speech.mdb_id,
                ROSTER_PATH.name,
            )
            return
        speech.reattributed_from = speech.party_id
        speech.party_id = found

    def _resolve(self, speech: Speech, protocol_party: Optional[str]) -> Optional[str]:
        if protocol_party is not None:
            return protocol_party
        if speech.mdb_id and speech.mdb_id in self.stammdaten:
            slug = party_to_slug(self.stammdaten[speech.mdb_id])
            if slug != PARTY_SLUG_QUARANTINE:
                return slug
        outside = self.roster.find(speech.mdb_id, speech.speaker)
        if outside is None:
            return None
        if speech.role is None:
            speech.role = outside.office
        return outside.party


def _protocol_party(speech: Speech) -> Optional[str]:
    """The slug of the protocol's ``<fraktion>``; None when it names none we
    know."""
    if not speech.protocol_fraktion:
        return None
    slug = party_to_slug(speech.protocol_fraktion)
    return None if slug == PARTY_SLUG_QUARANTINE else slug


def _same_fraktion(a: str, b: str) -> bool:
    # The protocol names the Union Fraktion; the corpus may know the member
    # is CSU.
    union = {"cdu", "csu"}
    return a == b or (a in union and b in union)
