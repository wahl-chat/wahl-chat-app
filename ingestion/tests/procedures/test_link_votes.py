# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

import pytest

from ingestion.procedures.link_votes import VoteTotals, resolve_vote, tally_distance

from .conftest import load

SCHULDENBREMSE = VoteTotals(yes=512, no=206, abstain=0)


def _resolve(totals: VoteTotals, drucksachen: list[str], *, days=None, by_number=None):
    days = (
        days
        if days is not None
        else {date.fromisoformat(d): p for d, p in load("positions_2025_03_18").items()}
    )
    by_number = (
        by_number if by_number is not None else load("drucksache_vorgaenge_2025_03_18")
    )
    return resolve_vote(
        voted_on=date(2025, 3, 18),
        totals=totals,
        drucksachen=drucksachen,
        positions_on=lambda day: days.get(day, []),
        drucksache_vorgaenge=lambda numbers: {
            n: by_number[n] for n in numbers if n in by_number
        },
    )


def test_tally_parsing_allows_embedded_text_swaps_and_slack() -> None:
    totals = VoteTotals(398, 41, 248)
    assert tally_distance("Artikel 7; 398:41:248", totals) == 0
    assert tally_distance("41:398:248", totals) == 0  # vote on a reject recommendation
    assert tally_distance("400:39:250", totals) == 6
    assert tally_distance("420:41:248", totals) is None
    assert tally_distance("Geschäftsordnungsantrag der AfD", totals) is None


def test_the_schuldenbremse_vote_links_by_tally_and_drucksache() -> None:
    result = _resolve(SCHULDENBREMSE, ["20/15096"])
    assert result.vorgang_ids == ["320784"]
    assert result.method == "tally_drucksache"


def test_a_wrong_drucksache_does_not_override_the_tally() -> None:
    result = _resolve(SCHULDENBREMSE, ["20/99999"])
    assert result.vorgang_ids == ["320784"] and result.method == "tally"


def test_without_a_matching_tally_the_drucksache_decides() -> None:
    result = _resolve(VoteTotals(1, 1, 1), ["20/15096"])
    assert result.vorgang_ids == ["320784"] and result.method == "drucksache_date"


def test_nothing_matching_gives_none() -> None:
    assert _resolve(VoteTotals(1, 1, 1), []).method == "none"


def test_a_dip_failure_propagates_so_the_vote_is_retried() -> None:
    def boom(day):
        raise RuntimeError("DIP down")

    with pytest.raises(RuntimeError):
        resolve_vote(
            voted_on=date(2025, 3, 18),
            totals=SCHULDENBREMSE,
            drucksachen=[],
            positions_on=boom,
            drucksache_vorgaenge=lambda n: {},
        )
