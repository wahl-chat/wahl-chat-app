# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from ingestion.feed import eval as feed_eval
from ingestion.feed.builder import plan_days
from tests.feed.samples import BUNDESTAG, DAY, default_speeches, sittings, speech


def test_question_time_and_two_party_items_are_not_picked() -> None:
    payloads = default_speeches() + [
        speech(
            f"q{n}",
            speaker=name,
            party=party,
            text="Frage.",
            agenda="top9",
            title="Fragestunde",
        )
        for n, (name, party) in enumerate(
            [("Ute", "spd"), ("Vera", "afd"), ("Wim", "gruene")]
        )
    ]
    plans = plan_days(BUNDESTAG, [], sittings(payloads))
    # TOP 1 has two Fraktionen (CSU sits with the CDU), TOP 2 one.
    assert feed_eval.select_debates(BUNDESTAG, plans, 5) == []


def test_picks_spread_from_shortest_to_longest() -> None:
    payloads = [
        speech(
            f"{agenda}-{n}",
            speaker=f"Person {agenda} {n}",
            party=party,
            text="Rede.",
            agenda=agenda,
            title=agenda,
        )
        for agenda, size in [("top1", 3), ("top2", 4), ("top3", 5), ("top4", 6)]
        for n, party in enumerate(
            ["spd", "cdu", "afd", "gruene", "linke", "spd"][:size]
        )
    ]
    plans = plan_days(BUNDESTAG, [], sittings(payloads))
    chosen = feed_eval.select_debates(BUNDESTAG, plans, 2)
    assert [u.agenda.slug for u, _ in chosen] == ["top1", "top4"]


def test_a_frozen_debate_rebuilds_the_same_unit() -> None:
    [plan] = plan_days(BUNDESTAG, [], sittings())
    unit = plan.debates[0]
    frozen = feed_eval.snapshot(unit, DAY)
    rebuilt_plan, rebuilt = feed_eval.unit_from_snapshot(frozen)
    assert rebuilt.item_id == unit.item_id
    assert rebuilt_plan.edition_id == plan.edition_id
    assert rebuilt.agenda.ordered
    assert [(s.speaker, s.party_id, s.text) for s in rebuilt.agenda.speeches] == [
        (s.speaker, s.party_id, s.text) for s in unit.agenda.speeches
    ]


def test_only_checked_gold_counts_unless_asked() -> None:
    entries = {
        "spd": {"position": "Fordern mehr.", "checked_by": "rf"},
        "cdu": {"position": "Lehnen ab.", "checked_by": None},
        "afd": {"position": "", "checked_by": "rf"},
    }
    assert feed_eval._gold_sentences(entries, False) == {"spd": "Fordern mehr."}
    assert set(feed_eval._gold_sentences(entries, True)) == {"spd", "cdu"}


def test_the_report_fails_on_a_missing_or_disagreeing_position() -> None:
    complete = feed_eval.DebateScore("a", ["spd"], {"spd": "x"}, {"spd": (True, "")})
    assert feed_eval.report([complete]) == 0
    missing = feed_eval.DebateScore("b", ["spd", "cdu"], {"spd": "x"})
    assert feed_eval.report([complete, missing]) == 1
    wrong = feed_eval.DebateScore("c", ["spd"], {"spd": "x"}, {"spd": (False, "")})
    assert feed_eval.report([wrong]) == 1
