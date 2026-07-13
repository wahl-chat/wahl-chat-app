# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for mappers/stance.py — covers Req 5, Req 6, Req 10.

build_qsp / TestBuildQsp removed — src/matcher/ deleted; the
QuestionStancePair type no longer exists. The three surviving pure functions
(aggregate_fraction_tallies, derive_stance, fraction_to_party_slug) are tested
below.

Tests defined here:
  - test_derive_stance_agree: yes is the dominant bucket
  - test_derive_stance_disagree: no is the dominant bucket
  - test_derive_stance_neutral_abstain: abstain is the dominant bucket
  - test_derive_stance_absent: no_show is the dominant bucket (fraktionslos case)
  - test_derive_stance_tie: exact top-two tie resolves to neutral (Pitfall 6)
  - test_aggregate_skips_empty_fraction: votes with fraction=[] are skipped (Req 6)
  - test_fraction_to_party_slug_unmapped: unknown fraction_id -> "unbekannt" quarantine
  - test_golden_record_3602: poll 3602 full 709-vote fixture reproduces the exact
    per-fraction stances (Req 10, golden-record assertion)

All tests are pure (no I/O, no Firestore, no network) — stance.py itself must be
I/O-free (no firestore/requests/firebase imports).
"""

from __future__ import annotations


from src.ingestion.connectors.abgeordnetenwatch.mappers.stance import (
    aggregate_fraction_tallies,
    derive_stance,
    fraction_to_party_slug,
)


# ---------------------------------------------------------------------------
# derive_stance — 5 outcomes + tie (Req 5)
# ---------------------------------------------------------------------------


class TestDeriveStance:
    def test_agree(self) -> None:
        """Yes is the dominant bucket -> agree (SPD case: 144 yes, 0 no, 0 abstain, 8 no_show)."""
        assert derive_stance(144, 0, 0, 8) == "agree"

    def test_disagree(self) -> None:
        """No is the dominant bucket -> disagree (FDP case: 0 yes, 75 no, 0 abstain, 5 no_show)."""
        assert derive_stance(0, 75, 0, 5) == "disagree"

    def test_neutral_abstain(self) -> None:
        """Abstain is the dominant bucket -> neutral (GRÜNEN case: 0,1,59,7)."""
        assert derive_stance(0, 1, 59, 7) == "neutral"

    def test_absent(self) -> None:
        """no_show is the dominant bucket -> absent (fraktionslos case: 0,2,0,4)."""
        assert derive_stance(0, 2, 0, 4) == "absent"

    def test_tie_top_two_equal(self) -> None:
        """Exact tie between two buckets -> neutral (Pitfall 6 non-determinism guard)."""
        assert derive_stance(5, 5, 0, 0) == "neutral"

    def test_tie_preserves_locked_rule(self) -> None:
        """Tie rule holds regardless of which bucket names are tied."""
        assert derive_stance(0, 0, 3, 3) == "neutral"
        assert derive_stance(10, 10, 5, 5) == "neutral"


# ---------------------------------------------------------------------------
# aggregate_fraction_tallies — Req 6 degenerate-input guard
# ---------------------------------------------------------------------------


class TestAggregateFractionTallies:
    def test_skips_empty_fraction_list(self) -> None:
        """Votes with fraction=[] (not a dict) are silently skipped (Req 6)."""
        votes = [
            {"fraction": [], "vote": "no_show"},
            {"fraction": {"id": 22, "entity_type": "fraction", "label": "SPD"}, "vote": "yes"},
        ]
        tallies = aggregate_fraction_tallies(votes)
        assert 22 in tallies, "SPD fraction (id=22) should be tallied"
        assert tallies[22]["yes"] == 1
        assert tallies[22]["no_show"] == 0
        # The empty-fraction vote must NOT produce a tally entry
        assert len(tallies) == 1, "Empty-fraction vote must be skipped, not included"

    def test_skips_none_fraction(self) -> None:
        """Votes with fraction=None are also skipped without raising."""
        votes = [
            {"fraction": None, "vote": "abstain"},
            {"fraction": {"id": 14, "entity_type": "fraction", "label": "FDP"}, "vote": "no"},
        ]
        tallies = aggregate_fraction_tallies(votes)
        assert 14 in tallies
        assert tallies[14]["no"] == 1
        assert len(tallies) == 1

    def test_sums_counts_correctly(self) -> None:
        """Tallies accumulate yes/no/abstain/no_show counts per fraction."""
        frac = {"id": 81, "entity_type": "fraction", "label": "CDU/CSU"}
        votes = [
            {"fraction": frac, "vote": "yes"},
            {"fraction": frac, "vote": "yes"},
            {"fraction": frac, "vote": "abstain"},
            {"fraction": frac, "vote": "no_show"},
        ]
        tallies = aggregate_fraction_tallies(votes)
        assert tallies[81]["yes"] == 2
        assert tallies[81]["abstain"] == 1
        assert tallies[81]["no_show"] == 1
        assert tallies[81]["no"] == 0

    def test_unknown_vote_token_is_skipped(self) -> None:
        """An unexpected vote token is skip-and-warned, never crashes."""
        frac = {"id": 22, "entity_type": "fraction", "label": "SPD"}
        votes = [
            {"fraction": frac, "vote": "yes"},
            {"fraction": frac, "vote": "enthalten"},  # unknown enum value
            {"fraction": frac, "vote": "no"},
        ]
        # Must not raise — the unknown token is dropped.
        tallies = aggregate_fraction_tallies(votes)
        assert tallies[22]["yes"] == 1
        assert tallies[22]["no"] == 1
        # The unknown token contributes to no bucket.
        assert tallies[22]["abstain"] == 0
        assert tallies[22]["no_show"] == 0

    def test_missing_vote_key_is_skipped(self) -> None:
        """A vote dict missing the 'vote' key is skip-and-warned, not KeyError."""
        frac = {"id": 22, "entity_type": "fraction", "label": "SPD"}
        votes = [
            {"fraction": frac},  # no "vote" key at all
            {"fraction": frac, "vote": "yes"},
            {"fraction": frac, "vote": None},  # explicit null
        ]
        tallies = aggregate_fraction_tallies(votes)
        assert tallies[22]["yes"] == 1
        assert sum(
            tallies[22][k] for k in ("yes", "no", "abstain", "no_show")
        ) == 1, "Only the single valid 'yes' vote should be counted"

    def test_fraction_missing_id_is_skipped(self) -> None:
        """A fraction dict missing 'id' is skip-and-warned, not KeyError."""
        votes = [
            {"fraction": {"entity_type": "fraction", "label": "SPD"}, "vote": "yes"},
            {"fraction": {"id": 14, "label": "FDP"}, "vote": "no"},
        ]
        tallies = aggregate_fraction_tallies(votes)
        # Only the fraction WITH an id is tallied.
        assert set(tallies.keys()) == {14}
        assert tallies[14]["no"] == 1

    def test_all_invalid_votes_yields_empty_tallies(self) -> None:
        """A poll of only-malformed votes yields {} (so the connector skips it)."""
        frac = {"id": 22, "label": "SPD"}
        votes = [
            {"fraction": frac, "vote": "bogus"},
            {"fraction": frac, "vote": None},
        ]
        tallies = aggregate_fraction_tallies(votes)
        assert tallies == {}

    def test_label_selection_is_deterministic(self) -> None:
        """The stored fraction label is the lexicographically smallest, order-independent."""
        votes_order_a = [
            {"fraction": {"id": 41, "label": "DIE LINKE (Gruppe)"}, "vote": "no"},
            {"fraction": {"id": 41, "label": "DIE LINKE"}, "vote": "no"},
        ]
        votes_order_b = [
            {"fraction": {"id": 41, "label": "DIE LINKE"}, "vote": "no"},
            {"fraction": {"id": 41, "label": "DIE LINKE (Gruppe)"}, "vote": "no"},
        ]
        tallies_a = aggregate_fraction_tallies(votes_order_a)
        tallies_b = aggregate_fraction_tallies(votes_order_b)
        # Both orders must select the same (lexicographically smallest) label.
        assert tallies_a[41]["fraction"]["label"] == "DIE LINKE"
        assert tallies_b[41]["fraction"]["label"] == "DIE LINKE"
        assert tallies_a[41]["no"] == 2 == tallies_b[41]["no"]


# ---------------------------------------------------------------------------
# fraction_to_party_slug — unmapped -> quarantine (Req 6)
# ---------------------------------------------------------------------------


class TestFractionToPartySlug:
    def test_mapped_fraction(self) -> None:
        """Known fraction_id resolves to the party slug."""
        fraction_map = {22: "spd", 14: "fdp"}
        assert fraction_to_party_slug(22, fraction_map) == "spd"
        assert fraction_to_party_slug(14, fraction_map) == "fdp"

    def test_unmapped_fraction_returns_unbekannt(self) -> None:
        """Unknown fraction_id returns quarantine slug 'unbekannt' (Req 6)."""
        fraction_map = {22: "spd"}
        assert fraction_to_party_slug(999, fraction_map) == "unbekannt"

    def test_empty_map_returns_unbekannt(self) -> None:
        """Empty map -> always quarantine."""
        assert fraction_to_party_slug(14, {}) == "unbekannt"


# ---------------------------------------------------------------------------
# Golden-record assertion — poll 3602 (Req 10)
# ---------------------------------------------------------------------------


# Verified per-fraction stances from the live API (poll 3602)
EXPECTED_3602_STANCES = {
    14: "disagree",   # FDP: 0 yes, 75 no, 0 abstain, 5 no_show
    22: "agree",      # SPD: 144 yes, 0 no, 0 abstain, 8 no_show
    41: "disagree",   # DIE LINKE: 0 yes, 57 no, 0 abstain, 12 no_show
    56: "disagree",   # AfD: 0 yes, 79 no, 0 abstain, 10 no_show
    81: "agree",      # CDU/CSU: 225 yes, 0 no, 4 abstain, 17 no_show
    153: "neutral",   # DIE GRÜNEN: 0 yes, 1 no, 59 abstain, 7 no_show
    231: "absent",    # fraktionslos: 0 yes, 2 no, 0 abstain, 4 no_show
}

EXPECTED_3602_TALLIES = {
    14:  {"yes": 0,   "no": 75, "abstain": 0,  "no_show": 5},
    22:  {"yes": 144, "no": 0,  "abstain": 0,  "no_show": 8},
    41:  {"yes": 0,   "no": 57, "abstain": 0,  "no_show": 12},
    56:  {"yes": 0,   "no": 79, "abstain": 0,  "no_show": 10},
    81:  {"yes": 225, "no": 0,  "abstain": 4,  "no_show": 17},
    153: {"yes": 0,   "no": 1,  "abstain": 59, "no_show": 7},
    231: {"yes": 0,   "no": 2,  "abstain": 0,  "no_show": 4},
}


class TestGoldenRecord3602:
    def test_aggregate_tallies_match_research(self, aw_poll_3602_votes: dict) -> None:
        """aggregate_fraction_tallies on the 710-vote fixture matches the verified tally table."""
        votes = aw_poll_3602_votes["data"]
        tallies = aggregate_fraction_tallies(votes)

        for frac_id, expected in EXPECTED_3602_TALLIES.items():
            assert frac_id in tallies, f"frac_id={frac_id} missing from tallies"
            for key in ("yes", "no", "abstain", "no_show"):
                assert tallies[frac_id][key] == expected[key], (
                    f"frac_id={frac_id} {key}: "
                    f"got {tallies[frac_id][key]}, expected {expected[key]}"
                )

    def test_empty_fraction_vote_is_skipped(self, aw_poll_3602_votes: dict) -> None:
        """The fixture contains one fraction=[] vote; it must be silently skipped."""
        votes = aw_poll_3602_votes["data"]
        empty_fraction_votes = [v for v in votes if v.get("fraction") == []]
        assert len(empty_fraction_votes) >= 1, "Fixture must contain at least one fraction=[] vote"

        tallies = aggregate_fraction_tallies(votes)
        # Only the 7 real fractions should appear — the empty-fraction vote must be absent
        assert set(tallies.keys()) == set(EXPECTED_3602_TALLIES.keys()), (
            f"Expected frac_ids {set(EXPECTED_3602_TALLIES.keys())}, got {set(tallies.keys())}"
        )

    def test_derive_stances_match_research(self, aw_poll_3602_votes: dict) -> None:
        """derive_stance on each fraction's tally matches the verified expected stance."""
        votes = aw_poll_3602_votes["data"]
        tallies = aggregate_fraction_tallies(votes)

        for frac_id, expected_stance in EXPECTED_3602_STANCES.items():
            t = tallies[frac_id]
            actual_stance = derive_stance(t["yes"], t["no"], t["abstain"], t["no_show"])
            assert actual_stance == expected_stance, (
                f"frac_id={frac_id}: expected stance '{expected_stance}', got '{actual_stance}'"
            )

    def test_fraktionslos_is_absent(self, aw_poll_3602_votes: dict) -> None:
        """fraktionslos (frac_id=231, yes=0,no=2,abstain=0,no_show=4) -> absent."""
        votes = aw_poll_3602_votes["data"]
        tallies = aggregate_fraction_tallies(votes)
        t = tallies[231]
        assert derive_stance(t["yes"], t["no"], t["abstain"], t["no_show"]) == "absent"

    def test_poll_fixture_metadata(self, aw_poll_3602_poll: dict) -> None:
        """The poll fixture contains the expected metadata fields."""
        poll = aw_poll_3602_poll["data"]
        assert poll["id"] == 3602
        assert poll["field_poll_date"] == "2020-05-14"
        assert poll["field_legislature"]["id"] == 111
        assert len(poll["field_topics"]) == 3
        # First topic is Gesundheit -> topic_id "aw:gesundheit"
        first_topic_url = poll["field_topics"][0]["abgeordnetenwatch_url"]
        assert first_topic_url.endswith("/gesundheit")
