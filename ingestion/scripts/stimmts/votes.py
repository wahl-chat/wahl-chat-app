"""From Abgeordnetenwatch's per-member votes to a puzzle's parties and counts."""

from __future__ import annotations

import re
from html import unescape

from ingestion.connectors.abgeordnetenwatch.mappers.stance import (
    aggregate_fraction_tallies,
)
from ingestion.party_slugs import CANONICAL_PARTY_SLUGS, normalize_party_label

# The Fraktionen of the 21st Bundestag, left to right, as the game requires.
SEATING_ORDER = ["linke", "spd", "gruene", "cdu", "afd"]
BUNDESTAG_SEATS = 630
# The game refuses a vote where a Fraktion split more than this (validate.ts).
MIN_PARTY_UNITY = 0.8

ANSWERS = ("yes", "no", "abstain")


def party_slug(fraction_label: str) -> str | None:
    """'BÜNDNIS 90/DIE GRÜNEN (Bundestag 2025 - 2029)' becomes 'gruene'."""
    name = fraction_label.split(" (")[0]
    return CANONICAL_PARTY_SLUGS.get(normalize_party_label(name))


def tally_parties(votes: list[dict]) -> tuple[list[dict], int]:
    """The five Fraktionen in seating order, and the members without one.

    A party's answer is the option most of its members chose; `unity` is that
    option's share of the votes cast, which the game needs to be 80 percent.
    """
    counts: dict[str, dict[str, int]] = {}
    unaffiliated = 0
    for tally in aggregate_fraction_tallies(votes).values():
        slug = party_slug(str(tally["fraction"].get("label") or ""))
        members = tally["yes"] + tally["no"] + tally["abstain"] + tally["no_show"]
        if slug == "fraktionslos":
            unaffiliated += members
        elif slug in SEATING_ORDER:
            party = counts.setdefault(
                slug, {"yes": 0, "no": 0, "abstain": 0, "noShow": 0}
            )
            party["yes"] += tally["yes"]
            party["no"] += tally["no"]
            party["abstain"] += tally["abstain"]
            party["noShow"] += tally["no_show"]

    parties = []
    for slug in SEATING_ORDER:
        party = counts.get(slug, {"yes": 0, "no": 0, "abstain": 0, "noShow": 0})
        voted = sum(party[key] for key in ANSWERS)
        answer = max(ANSWERS, key=lambda key: party[key]) if voted else None
        unity = round(party[answer] / voted, 3) if answer else 0.0
        parties.append({"partyId": slug, "answer": answer, **party, "unity": unity})
    return parties, unaffiliated


def seats(parties: list[dict], unaffiliated: int) -> int:
    return unaffiliated + sum(
        party["yes"] + party["no"] + party["abstain"] + party["noShow"]
        for party in parties
    )


def vote_problems(parties: list[dict], unaffiliated: int) -> list[str]:
    """What would make the game's validator refuse this vote."""
    problems = [
        f"{party['partyId']} is split ({party['unity']:.0%} for one option)"
        for party in parties
        if party["unity"] < MIN_PARTY_UNITY
    ]
    total = seats(parties, unaffiliated)
    if total != BUNDESTAG_SEATS:
        problems.append(f"the seats add up to {total}, not {BUNDESTAG_SEATS}")
    return problems


def outcome_problem(parties: list[dict], accepted: bool | None) -> str | None:
    """Abgeordnetenwatch's outcome, when the counts contradict it.

    Its `field_accepted` has been wrong before. The counts leave out the
    members without a Fraktion, and some votes need more than a simple
    majority, so a mismatch is a note to check, not a correction.
    """
    yes = sum(party["yes"] for party in parties)
    no = sum(party["no"] for party in parties)
    if (yes > no) == bool(accepted):
        return None
    said = "accepted" if accepted else "rejected"
    return (
        f"Abgeordnetenwatch says {said}, but the Fraktionen voted {yes} Ja "
        f"to {no} Nein: check the outcome"
    )


def pattern(parties: list[dict]) -> str:
    """'NJNJN': each party's answer in seating order (J = Ja, E = Enthaltung)."""
    letters = {"yes": "J", "no": "N", "abstain": "E", None: "-"}
    return "".join(letters[party["answer"]] for party in parties)


def intro_text(html: str) -> str:
    """The poll's description as plain text (it gives the result away)."""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def drucksache_urls(html: str) -> list[str]:
    """The Drucksachen the poll's description links to."""
    return sorted(
        set(re.findall(r'href="(https://dserver\.bundestag\.de/btd/[^"]+)"', html))
    )
