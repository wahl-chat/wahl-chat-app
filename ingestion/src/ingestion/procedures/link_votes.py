# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Which procedure(s) a roll-call vote decided.

Primary: the vote's date (± 1 day) and its yes/no/abstain totals against the
tallies DIP records for that day's decisions. The Drucksachen
abgeordnetenwatch links are the cross-check and the fallback, because they
are wrong for a few percent of votes.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from wahlchat_common.procedures import LinkMethod

_TALLY = re.compile(r"(\d+)\s*:\s*(\d+)\s*:\s*(\d+)")
# Per-count slack: DIP and abgeordnetenwatch differ by late corrections.
TOLERANCE = 10


@dataclass(frozen=True)
class VoteTotals:
    yes: int
    no: int
    abstain: int


@dataclass(frozen=True)
class VoteLinkResult:
    vorgang_ids: list[str]
    method: LinkMethod


def totals_of(vote_results: list[dict[str, Any]]) -> VoteTotals:
    return VoteTotals(
        yes=sum(int(r.get("yes") or 0) for r in vote_results),
        no=sum(int(r.get("no") or 0) for r in vote_results),
        abstain=sum(int(r.get("abstain") or 0) for r in vote_results),
    )


def tally_distance(text: str, totals: VoteTotals) -> Optional[int]:
    """Smallest distance between the vote and any tally in DIP's note.

    Yes and no may be swapped (the house votes on a committee recommendation
    to reject); each count must be within ``TOLERANCE``. None when no tally
    in the text is close enough.
    """
    best: Optional[int] = None
    for y, n, a in _TALLY.findall(text or ""):
        counts = (int(y), int(n), int(a))
        for yes, no in ((counts[0], counts[1]), (counts[1], counts[0])):
            diffs = (
                abs(yes - totals.yes),
                abs(no - totals.no),
                abs(counts[2] - totals.abstain),
            )
            if max(diffs) <= TOLERANCE:
                distance = sum(diffs)
                best = distance if best is None else min(best, distance)
    return best


def _plenary_vorgaenge(positions: list[dict[str, Any]]) -> set[str]:
    return {
        str(p["vorgang_id"])
        for p in positions
        if (p.get("fundstelle") or {}).get("dokumentart") == "Plenarprotokoll"
    }


def resolve_vote(
    *,
    voted_on: date,
    totals: VoteTotals,
    drucksachen: list[str],
    positions_on: Callable[[date], list[dict[str, Any]]],
    drucksache_vorgaenge: Callable[[list[str]], dict[str, list[str]]],
) -> VoteLinkResult:
    """Link one vote. Raises when DIP can't be read, so the caller retries."""
    days = [voted_on + timedelta(days=d) for d in (0, -1, 1)]
    positions = [p for day in days for p in positions_on(day)]

    best: Optional[int] = None
    tallied: set[str] = set()
    for position in positions:
        for decision in position.get("beschlussfassung") or []:
            distance = tally_distance(
                decision.get("abstimm_ergebnis_bemerkung") or "", totals
            )
            if distance is None:
                continue
            vid = str(position["vorgang_id"])
            if best is None or distance < best:
                best, tallied = distance, {vid}
            elif distance == best:
                tallied.add(vid)

    named: set[str] = set()
    if drucksachen:
        by_number = drucksache_vorgaenge(drucksachen)
        named = {vid for vids in by_number.values() for vid in vids}
        named &= _plenary_vorgaenge(positions)

    if tallied:
        method: LinkMethod = "tally_drucksache" if tallied & named else "tally"
        return VoteLinkResult(sorted(tallied), method)
    if named:
        return VoteLinkResult(sorted(named), "drucksache_date")
    return VoteLinkResult([], "none")
