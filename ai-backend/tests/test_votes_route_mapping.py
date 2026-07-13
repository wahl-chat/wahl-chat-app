# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for the /votes route's vote_record payload → Vote mapping.

Tests defined here:
  - test_chunk_payload_to_vote_maps_correctly: a well-formed vote_record chunk
    payload maps to a Vote instance with the expected field values.
  - test_chunk_payload_to_vote_skips_non_participant: a payload where the target
    party has no entry in vote_results returns None (graceful skip, no 500).
  - test_chunk_payload_to_vote_malformed_returns_none: a payload with no
    vote_results in meta returns None (graceful skip, no 500).
  - test_chunk_payload_to_vote_no_meta_returns_none: a payload without a meta
    key at all returns None (graceful skip, no 500).

These tests run entirely in-process — no Qdrant or external API required.
"""


from src.routes.voting_behavior import _chunk_payload_to_vote
from src.models.vote import Vote


# ---------------------------------------------------------------------------
# Test fixtures — minimal ChunkRecord-shaped vote_record payloads
# (verified against the live wahlchat_chunks_dev store payload shape)
# ---------------------------------------------------------------------------

_VOTE_RESULTS_GOOD = [
    {"party_id": "spd", "stance": "agree", "yes": 100, "no": 5, "abstain": 2, "no_show": 3},
    {"party_id": "cdu", "stance": "disagree", "yes": 10, "no": 90, "abstain": 5, "no_show": 0},
]

_GOOD_PAYLOAD = {
    "source_type": "vote_record",
    "party_id": "_all",  # vote_record sentinel (no single tenant)
    "party_ids": ["spd", "cdu"],
    "text": "Mindestlohnerhöhung auf 15 Euro - Abstimmung im Bundestag",
    "citation_title": "Abstimmung: Mindestlohn",
    "citation_url": "https://www.abgeordnetenwatch.de/bundestag/abstimmungen/mindestlohn",
    "publish_date": "2024-03-15T00:00:00",
    "source_item_id": "aw_poll:12345",
    "external_id": "aw_poll:12345",
    "meta": {
        "vote_results": _VOTE_RESULTS_GOOD,
        "motion_outcome": "passed",
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_chunk_payload_to_vote_maps_correctly() -> None:
    """A well-formed vote_record payload maps to a Vote with correct fields.

    Verification:
    1. Call _chunk_payload_to_vote with a good payload and party_id='spd'.
    2. Assert Vote instance is returned (not None).
    3. Assert key fields map correctly from payload → Vote schema.
    4. Assert voting_results.by_party contains entries for both spd and cdu.
    5. Assert voting_results.overall totals match the sum of by_party tallies.
    """
    vote = _chunk_payload_to_vote(_GOOD_PAYLOAD, "spd")

    assert vote is not None, (
        "W2: _chunk_payload_to_vote returned None for a well-formed payload"
    )
    assert isinstance(vote, Vote), (
        f"W2: expected Vote instance, got {type(vote)!r}"
    )

    # Field mapping checks
    assert vote.title == "Abstimmung: Mindestlohn", (
        f"W2: title mismatch — got {vote.title!r}"
    )
    assert vote.url == "https://www.abgeordnetenwatch.de/bundestag/abstimmungen/mindestlohn", (
        f"W2: url mismatch — got {vote.url!r}"
    )
    assert vote.date == "2024-03-15", (
        f"W2: date mismatch — got {vote.date!r} (expected YYYY-MM-DD)"
    )
    assert vote.subtitle == "passed", (
        f"W2: subtitle/motion_outcome mismatch — got {vote.subtitle!r}"
    )
    assert vote.id == "aw_poll:12345", (
        f"W2: id mismatch — got {vote.id!r}"
    )

    # by_party checks
    party_ids_in_result = {bp.party for bp in vote.voting_results.by_party}
    assert "spd" in party_ids_in_result, (
        "W2: 'spd' missing from voting_results.by_party"
    )
    assert "cdu" in party_ids_in_result, (
        "W2: 'cdu' missing from voting_results.by_party"
    )

    spd_entry = next(bp for bp in vote.voting_results.by_party if bp.party == "spd")
    assert spd_entry.yes == 100, f"W2: spd yes count mismatch — got {spd_entry.yes}"
    assert spd_entry.no == 5, f"W2: spd no count mismatch — got {spd_entry.no}"

    # overall totals = sum of by_party
    assert vote.voting_results.overall.yes == 110, (
        f"W2: overall.yes should be 110 (100+10), got {vote.voting_results.overall.yes}"
    )
    assert vote.voting_results.overall.no == 95, (
        f"W2: overall.no should be 95 (5+90), got {vote.voting_results.overall.no}"
    )


def test_chunk_payload_to_vote_skips_non_participant() -> None:
    """Party not in vote_results → None (graceful skip, no 500).

    Verification:
    1. Call _chunk_payload_to_vote with party_id='fdp' which has no entry in
       vote_results.
    2. Assert None is returned.
    """
    vote = _chunk_payload_to_vote(_GOOD_PAYLOAD, "fdp")

    assert vote is None, (
        "W2: expected None when party='fdp' has no entry in vote_results — "
        f"got {vote!r}"
    )


def test_chunk_payload_to_vote_malformed_returns_none() -> None:
    """Empty vote_results in meta → None (graceful skip, no 500).

    Verification:
    1. Call _chunk_payload_to_vote with a payload that has meta.vote_results=[].
    2. Assert None is returned (not a Vote, not a raised exception).
    """
    payload = {**_GOOD_PAYLOAD, "meta": {"vote_results": [], "motion_outcome": "passed"}}

    vote = _chunk_payload_to_vote(payload, "spd")

    assert vote is None, (
        "W2: expected None for empty vote_results — got {!r}".format(vote)
    )


def test_chunk_payload_to_vote_no_meta_returns_none() -> None:
    """Payload without meta key → None (graceful skip, no 500).

    Verification:
    1. Call _chunk_payload_to_vote with a payload that has no 'meta' key.
    2. Assert None is returned.
    """
    payload = {k: v for k, v in _GOOD_PAYLOAD.items() if k != "meta"}

    vote = _chunk_payload_to_vote(payload, "spd")

    assert vote is None, (
        "W2: expected None for payload with no 'meta' key — got {!r}".format(vote)
    )
