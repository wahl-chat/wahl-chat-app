# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import asyncio
import time
from typing import Any

import pytest

from ingestion.feed.builder import (
    FeedBuilder,
    plan_days,
    speeches_block,
    vote_description,
)
from ingestion.feed.items import debate_input_hash
from ingestion.feed.models import FeedItem
from ingestion.feed.prompts import (
    DebateDraft,
    OpeningQuoteDraft,
    PositionCheckBatch,
    PositionsDraft,
    VoteEnrichmentBatch,
)
from ingestion.feed.reader import assemble_speeches
from tests.feed.samples import (
    BUNDESTAG,
    DAY,
    FakeLLM,
    build,
    default_speeches,
    sittings,
    speech,
    vote,
)


def _debate(items: list[FeedItem], slug: str = "top1") -> FeedItem:
    return next(i for i in items if i.id.endswith(f"_d45-{slug}"))


def test_every_agenda_item_and_every_poll_is_one_item() -> None:
    items = build(FakeLLM())
    assert [i.id for i in items] == [
        "bundestag_2026-09-24_d45-top1",
        "bundestag_2026-09-24_d45-top2",
        "bundestag_2026-09-24_v1",
        "bundestag_2026-09-24_v2",
    ]
    assert all(i.input_hash is not None for i in items)


def test_speeches_outside_any_agenda_item_are_no_debate() -> None:
    days = sittings(
        default_speeches()
        + [speech("s9", speaker="Eva", party="spd", text="Guten Morgen.", agenda="")]
    )
    [plan] = plan_days(BUNDESTAG, [], days)
    assert [u.item_id for u in plan.debates] == [
        "bundestag_2026-09-24_d45-top1",
        "bundestag_2026-09-24_d45-top2",
    ]


def test_two_sittings_on_one_day_keep_their_own_agenda_items() -> None:
    days = sittings(
        [
            speech("a", speaker="Anna", party="spd", text="x", session=45),
            speech("b", speaker="Bernd", party="cdu", text="y", session=46),
        ]
    )
    [plan] = plan_days(BUNDESTAG, [], days)
    assert [u.item_id for u in plan.debates] == [
        "bundestag_2026-09-24_d45-top1",
        "bundestag_2026-09-24_d46-top1",
    ]
    assert [p.protocol_id for p in plan.debates[1].protocols] == ["21/46"]


def test_a_debate_without_protocol_order_is_not_built() -> None:
    llm = FakeLLM()
    items = build(llm, days=sittings(ordered=False))
    assert [i.kind for i in items] == ["vote", "vote"]
    assert DebateDraft not in llm.calls


def test_the_model_sees_the_whole_debate_in_order() -> None:
    llm = FakeLLM()
    build(llm, votes=[])
    prompt = next(p for p in llm.prompts if "Wohnungsbau" in p and "Reden:" in p)
    speeches = prompt.split("Reden:\n", 1)[1]
    assert speeches.index("Anna (spd)") < speeches.index("Bernd (cdu)")
    assert speeches.index("Bernd (cdu)") < speeches.index("Clara (csu)")
    assert "Bauordnung" not in prompt


def test_a_long_debate_is_shortened_evenly_without_dropping_a_speech() -> None:
    speeches = assemble_speeches(
        [
            speech("a", speaker="Anna", party="spd", text="a " * 50_000),
            speech("b", speaker="Bernd", party="cdu", text="b " * 50_000),
            speech("c", speaker="Clara", party="afd", text="kurz"),
        ]
    )
    block = speeches_block(sorted(speeches, key=lambda s: s.source_item_id), 20_000)
    lines = block.splitlines()
    assert [line.split(" (")[0] for line in lines] == ["- Anna", "- Bernd", "- Clara"]
    assert len(block) < 30_000
    assert lines[2].endswith("kurz")


def test_every_fraktion_that_spoke_is_in_the_facts_from_the_source() -> None:
    debate = _debate(build(FakeLLM()))
    assert debate.debate is not None
    parties = {p.party_id: [s.name for s in p.speakers] for p in debate.debate.parties}
    # The CSU sits in the Union's Fraktion.
    assert parties == {"spd": ["Anna"], "cdu": ["Bernd", "Clara"]}
    assert [p.party_id for p in debate.content["de"].positions] == ["spd", "cdu"]


def test_a_missing_position_is_retried_for_that_fraktion_only() -> None:
    llm = FakeLLM(omit=("cdu",))
    debate = _debate(build(llm, votes=[]))
    positions = {p.party_id: p.text for p in debate.content["de"].positions}
    assert positions["cdu"] == "Retry Position cdu."
    retry = llm.prompts[llm.calls.index(PositionsDraft)]
    assert "keine andere: cdu." in retry
    assert "Anna" not in retry
    assert debate.input_hash is not None


def test_a_fraktion_still_missing_is_listed_without_a_sentence_and_retried_later() -> (
    None
):
    debate = _debate(build(FakeLLM(omit=("cdu",), retry_omit=("cdu",))))
    assert debate.debate is not None
    assert "cdu" in [p.party_id for p in debate.debate.parties]
    assert [p.party_id for p in debate.content["de"].positions] == ["spd"]
    assert debate.input_hash is None


def test_an_unsupported_position_is_never_published() -> None:
    llm = FakeLLM(reject=("Fordern Position spd",))
    debate = _debate(build(llm, votes=[]))
    positions = {p.party_id: p.text for p in debate.content["de"].positions}
    # The check refused the first sentence, the retry was checked again.
    assert positions == {"spd": "Retry Position spd.", "cdu": "Fordern Position cdu."}
    checks = [p for c, p in zip(llm.calls, llm.prompts) if c is PositionCheckBatch]
    assert any("Retry Position spd" in p for p in checks)


def test_a_failed_check_publishes_no_unchecked_sentence() -> None:
    debate = _debate(build(FakeLLM(fail=(PositionCheckBatch,))))
    assert debate.content["de"].positions == []
    assert debate.input_hash is None


def test_positions_of_parties_that_did_not_speak_are_dropped() -> None:
    debate = _debate(build(FakeLLM()), "top2")
    assert [p.party_id for p in debate.content["de"].positions] == ["afd"]


def test_fraktionslose_speakers_need_no_position() -> None:
    days = sittings(
        default_speeches()[:1]
        + [speech("s9", speaker="Fritz", party="fraktionslos", text="Ich nicht.")]
    )
    debate = _debate(build(FakeLLM(omit=("fraktionslos",)), days=days, votes=[]))
    assert debate.input_hash is not None


def test_a_failed_debate_is_left_for_the_next_run_and_votes_still_build() -> None:
    items = build(FakeLLM(fail=(DebateDraft,)))
    assert [i.kind for i in items] == ["vote", "vote"]


def test_a_failed_vote_enrichment_falls_back_and_stays_retryable() -> None:
    items = build(FakeLLM(fail=(VoteEnrichmentBatch,)), days={})
    assert [i.content["de"].headline for i in items] == ["Antrag 1", "Antrag 2"]
    assert all(i.topics == ["other"] and i.input_hash is None for i in items)


def test_votes_carry_texts_parties_and_the_source_description() -> None:
    items = build(FakeLLM(), days={})
    first = items[0]
    assert first.content["de"].headline == "Kurz V1"
    assert first.topics == ["housing_rent", "economy_finance"]
    assert first.content["de"].suggested_questions == [
        "Was heißt das für mich?",
        "Wer war dagegen?",
        "Was kostet das?",
    ]
    assert first.vote is not None
    names = {p.party_id: (p.name, p.yes) for p in first.vote.parties}
    assert names["cdu"] == ("CDU/CSU", 200)
    assert names["fraktionslos"][0] == "Fraktionslos"
    assert first.vote.description == "Worum es geht."


def test_the_first_speech_opens_the_debate() -> None:
    debate = _debate(build(FakeLLM()))
    assert debate.debate is not None
    assert debate.debate.opened_by == "spd"
    assert debate.debate.citations[0].speaker == "Anna"
    assert debate.debate.video_url == "https://video/s1.mp4"
    quote = debate.debate.opening_quote
    assert quote is not None and (quote.speaker, quote.text) == (
        "Anna",
        "Wir brauchen mehr Wohnungen.",
    )


@pytest.mark.parametrize(
    ("drafted", "kept"),
    [
        (
            OpeningQuoteDraft(speaker="anna", quote="„Wir brauchen  mehr Wohnungen.“"),
            True,
        ),
        (
            OpeningQuoteDraft(
                speaker="Anna (spd)", quote="Wir brauchen mehr Wohnungen."
            ),
            True,
        ),
        (OpeningQuoteDraft(speaker="Anna", quote="Wir müssen viel mehr bauen."), False),
        (
            OpeningQuoteDraft(speaker="Bernd", quote="Wir brauchen mehr Wohnungen."),
            False,
        ),
        (OpeningQuoteDraft(speaker="Anna", quote=" ".join(["Wohnungen"] * 41)), False),
    ],
)
def test_the_opening_quote_is_kept_only_when_verbatim(
    drafted: OpeningQuoteDraft, kept: bool
) -> None:
    debate = _debate(build(FakeLLM(quote=drafted), votes=[]))
    assert debate.debate is not None
    assert (debate.debate.opening_quote is not None) is kept


def test_heat_is_clamped_and_key_points_need_exactly_three() -> None:
    hot = _debate(build(FakeLLM(heat=9), votes=[]))
    assert hot.debate is not None and hot.debate.heat == 5
    cold = _debate(build(FakeLLM(heat=0, key_points=["a", "b"]), votes=[]))
    assert cold.debate is not None and cold.debate.heat == 1
    assert cold.content["de"].key_points == []


def test_debates_carry_up_to_two_distinct_topics_primary_first() -> None:
    topics: Any = ["housing_rent", "housing_rent", "social_labor", "other"]
    assert _debate(build(FakeLLM(topics=topics), votes=[])).topics == [
        "housing_rent",
        "social_labor",
    ]


def test_debate_minutes_are_estimated_from_the_speech_text() -> None:
    debate = _debate(build(FakeLLM(), votes=[]))
    assert debate.debate is not None and debate.debate.debate_minutes == 1


def test_a_late_speech_changes_only_its_own_debate_hash() -> None:
    before = {
        u.item_id: u.input_hash
        for u in plan_days(BUNDESTAG, [vote(1)], sittings())[0].debates
    }
    late = default_speeches() + [
        speech("s5", speaker="Emil", party="afd", text="Nachtrag.", agenda="top2")
    ]
    after = {
        u.item_id: u.input_hash
        for u in plan_days(BUNDESTAG, [vote(1)], sittings(late))[0].debates
    }
    assert (
        after["bundestag_2026-09-24_d45-top1"]
        == before["bundestag_2026-09-24_d45-top1"]
    )
    assert (
        after["bundestag_2026-09-24_d45-top2"]
        != before["bundestag_2026-09-24_d45-top2"]
    )


def test_the_debate_hash_does_not_depend_on_speech_order() -> None:
    item = sittings()[DAY].agenda_items[0]
    reordered = sittings()[DAY].agenda_items[0]
    reordered.speeches.reverse()
    assert debate_input_hash(item) == debate_input_hash(reordered)


def test_items_not_started_before_the_budget_ran_out_are_left_out() -> None:
    llm = FakeLLM()
    assert build(llm, out_of_time=lambda: True) == []
    assert llm.calls == []


def test_a_call_past_the_deadline_is_cut() -> None:
    async def slow(_messages: list, _schema: type) -> tuple[Any, str]:
        await asyncio.sleep(5)
        return None, "slow"

    builder = FeedBuilder(slow, deadline=time.monotonic() + 0.05)
    try:
        with pytest.raises(TimeoutError):
            builder.call("x", DebateDraft)
        with pytest.raises(TimeoutError):
            builder.call("x", DebateDraft)
    finally:
        builder.close()


def test_vote_description_takes_the_source_intro() -> None:
    assert vote_description(
        "Antrag 1\n\nThemen: Haushalt\n\nKontext: Worum es geht."
    ) == ("Worum es geht.")
    assert vote_description("Antrag ohne Kontext") is None


def test_vote_description_cuts_long_intros_at_a_sentence() -> None:
    intro = "Ein Satz. " * 400
    described = vote_description(f"Antrag\n\nKontext: {intro}")
    assert described is not None
    assert described.endswith(". …")
    assert len(described) <= 1503
