# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from typing import Any, Optional

import pytest
from wahlchat_common.answer_rules import CITATION_RULES, VOICE_RULES, language_rule

from ingestion.feed import bulk
from ingestion.feed.answers import (
    MAX_ANSWER_ATTEMPTS,
    AnswerBatch,
    needs_answers,
    renumber,
)
from ingestion.feed.builder import FeedBuilder, build_day, plan_days
from ingestion.feed.items import content_hash
from ingestion.feed.models import (
    FEED_FORMAT_VERSION,
    AnswerSource,
    FeedItem,
    SuggestedAnswer,
)
from ingestion.feed.translate import needs_translation, translate_items
from tests.feed.samples import (
    BUNDESTAG,
    DISPLAY,
    NOW,
    FakeLLM,
    build,
    sittings,
    vote,
)
from tests.feed.test_translate import FakeTranslator, _english

TOP1 = "bundestag_2026-09-24_d45-top1"
VOTE1 = "bundestag_2026-09-24_v1"


def _by_id(items: list[FeedItem]) -> dict[str, FeedItem]:
    return {i.id: i for i in items}


# --- format v7 ----------------------------------------------------------------


def test_an_item_stored_before_v7_still_validates() -> None:
    stored = build(FakeLLM())[0].model_dump(mode="json")
    stored["format_version"] = "6"
    del stored["debate"]["speech_ids"]
    del stored["content"]["de"]["suggested_answers"]
    item = FeedItem.model_validate(stored)
    assert item.debate is not None and item.debate.speech_ids == []
    assert item.content["de"].suggested_answers == []


def test_a_built_debate_carries_its_speech_ids_in_debate_order() -> None:
    items = _by_id(build(FakeLLM()))
    debate = items[TOP1].debate
    assert debate is not None
    assert debate.speech_ids == ["s1", "s2", "s3"]
    assert items[TOP1].format_version == FEED_FORMAT_VERSION == "7"


# --- answers --------------------------------------------------------------------


def test_every_question_gets_an_answer_with_a_source() -> None:
    for item in build(FakeLLM()):
        de = item.content["de"]
        assert de.suggested_questions
        assert len(de.suggested_answers) == len(de.suggested_questions)
        assert all(a and a.sources and "[1]" in a.text for a in de.suggested_answers)


def test_a_debate_answer_cites_the_speech_at_its_passage() -> None:
    llm = FakeLLM(answers={"F1": "Bernd will erst die Kosten prüfen [2]."})
    [answer] = _by_id(build(llm))[TOP1].content["de"].suggested_answers
    assert answer is not None
    assert answer.text == "Bernd will erst die Kosten prüfen [1]."
    [source] = answer.sources
    assert source.source_type == "parliamentary_speech"
    assert source.party_id == "cdu"
    assert source.source == "Bernd, 2026-09-24 (Video)"
    assert source.snippet == "Erst die Kosten prüfen."
    assert source.video_url is not None
    assert source.video_url.startswith("https://video/s2.mp4")
    assert source.pdf_url == "https://dserver.bundestag.de/btp/21/21045.pdf"
    assert source.document_publish_date == "2026-09-24"


def test_a_vote_answer_cites_the_vote_record() -> None:
    item = _by_id(build(FakeLLM()))[VOTE1]
    assert item.vote is not None
    for answer in item.content["de"].suggested_answers:
        assert answer.sources == [
            AnswerSource(
                source="Antrag 1",
                url="https://www.abgeordnetenwatch.de/poll/1",
                source_type="vote_record",
                document_publish_date="2026-09-24",
            )
        ]


def test_the_prompt_holds_the_shared_rules_and_the_sources() -> None:
    llm = FakeLLM()
    build(llm)
    prompts = [p for p, s in zip(llm.prompts, llm.calls) if s is AnswerBatch]
    assert len(prompts) == 4  # one per item
    for prompt in prompts:
        assert VOICE_RULES in prompt
        assert CITATION_RULES in prompt
        assert language_rule("de") in prompt
    debate = next(p for p in prompts if "agenda item" in p)
    assert "[1] Anna (spd): Wir brauchen mehr Wohnungen." in debate
    assert "[3] Clara (csu): Bayern baut schon." in debate
    assert "[F1] Was heißt das für mich?" in debate
    vote_prompt = next(p for p in prompts if "Antrag 1" in p)
    assert "CDU/CSU: 200 ja, 0 nein" in vote_prompt


def test_citations_are_renumbered_in_the_order_of_use() -> None:
    text, cited = renumber("Erst B [3], dann A [1, 3] und [9].", 3)
    assert (text, cited) == ("Erst B [1], dann A [2][1] und.", [3, 1])


def _answer_prompts(llm: FakeLLM) -> list[str]:
    return [p for p, s in zip(llm.prompts, llm.calls) if s is AnswerBatch]


def test_failed_answer_calls_leave_the_items_without_answers() -> None:
    llm = FakeLLM(fail=(AnswerBatch,))
    builder = FeedBuilder(llm)
    try:
        [plan] = plan_days(BUNDESTAG, [vote(1)], sittings())
        items = build_day(
            builder, BUNDESTAG, plan, plan.debates, plan.votes, {}, now=NOW
        )
        # The items stand, and the run is not marked failed for it.
        assert builder.failed == []
    finally:
        builder.close()
    assert len(items) == 3
    assert all(i.content["de"].suggested_answers == [] for i in items)
    assert all(i.content["de"].suggested_questions for i in items)
    # One retry each, counted as one run's attempt.
    assert len(_answer_prompts(llm)) == 6
    assert all(i.answer_attempts == 1 for i in items)


def test_a_failed_answer_call_is_retried_for_the_whole_batch() -> None:
    llm = FakeLLM(fail_first=(AnswerBatch,))
    items = build(llm)
    assert all(
        len(i.content["de"].suggested_answers)
        == len(i.content["de"].suggested_questions)
        and None not in i.content["de"].suggested_answers
        for i in items
    )
    retry = next(p for p in _answer_prompts(llm) if "was rejected" in p)
    assert "- The reply failed or could not be read." in retry


@pytest.mark.parametrize(
    ("answers", "problem"),
    [
        ({"F2": "Ohne Beleg."}, "- [F2] cited none of the numbered sources."),
        ({"F2": None}, "- [F2] had no answer."),
        ({"F2": "Falscher Beleg [7]."}, "- [F2] cited none of the numbered sources."),
    ],
)
def test_a_bad_answer_is_retried_alone_and_the_others_are_kept(
    answers: dict[str, Optional[str]], problem: str
) -> None:
    llm = FakeLLM(answers=answers)
    item = _by_id(build(llm, votes=[vote(1)]))[VOTE1]
    first, second, third = item.content["de"].suggested_answers
    assert first is not None and third is not None and second is None
    assert len(item.content["de"].suggested_questions) == 3
    assert item.answer_attempts == 1
    [retry] = [p for p in _answer_prompts(llm) if "was rejected" in p]
    assert problem in retry
    questions = retry.split("Questions:")[1].split("Questions already answered")[0]
    assert "[F2]" in questions and "[F1]" not in questions
    # The kept answers are shown for consistency, without their citations.
    assert "[F1] Antwort." in retry


def test_a_retry_can_fill_the_gap() -> None:
    llm = FakeLLM(answers={"F2": "Ohne Beleg."}, retry_answers={"F2": "Mit [1]."})
    item = _by_id(build(llm, votes=[vote(1)]))[VOTE1]
    answers = item.content["de"].suggested_answers
    assert [a.text if a else None for a in answers] == [
        "Antwort [1].",
        "Mit [1].",
        "Antwort [1].",
    ]


def test_a_call_cut_by_the_time_budget_is_not_an_attempt() -> None:
    llm = FakeLLM()

    async def slow(messages: list, schema: type) -> tuple[Any, str]:
        if schema is AnswerBatch:
            raise TimeoutError("time budget spent")
        return await llm(messages, schema)

    builder = FeedBuilder(slow)
    try:
        [plan] = plan_days(BUNDESTAG, [vote(1)], sittings())
        items = build_day(
            builder, BUNDESTAG, plan, plan.debates, plan.votes, DISPLAY, now=NOW
        )
    finally:
        builder.close()
    assert all(i.answer_attempts == 0 for i in items)
    assert all(needs_answers(i) for i in items)


def test_answers_are_part_of_the_hash_only_when_there_are_some() -> None:
    item = build(FakeLLM(fail=(AnswerBatch,)))[0]
    content = item.content["de"]
    assert content.source_hash == content_hash(content)
    answer = SuggestedAnswer(text="A [1].", sources=[AnswerSource(source="x")])
    answered = content.model_copy(update={"suggested_answers": [answer]})
    assert content_hash(answered) != content.source_hash
    gap = content.model_copy(update={"suggested_answers": [None, answer]})
    assert content_hash(gap) not in (content.source_hash, content_hash(answered))


def test_a_partly_answered_item_stores_its_gaps_as_null() -> None:
    item = _by_id(build(FakeLLM(answers={"F2": None}), votes=[vote(1)]))[VOTE1]
    stored = item.model_dump(mode="json")
    assert stored["content"]["de"]["suggested_answers"][1] is None
    assert FeedItem.model_validate(stored) == item
    assert item.content["de"].source_hash == content_hash(item.content["de"])


def test_answered_items_need_a_new_translation() -> None:
    plain = _by_id(build(FakeLLM(fail=(AnswerBatch,))))[TOP1]
    answered = _by_id(build(FakeLLM()))[TOP1]
    assert plain.content["de"].source_hash != answered.content["de"].source_hash


# --- translation ----------------------------------------------------------------


def _translate(items: list[FeedItem], **kwargs: Any) -> None:
    builder = FeedBuilder(FakeTranslator(**kwargs))
    try:
        translate_items(items, builder, now=NOW)
    finally:
        builder.close()


def test_translated_answers_keep_their_count_and_sources() -> None:
    items = build(FakeLLM())
    _translate(items)
    for item in items:
        de, en = item.content["de"], item.content["en"]
        assert [a.text for a in en.suggested_answers if a] == [
            _english(a.text) for a in de.suggested_answers if a
        ]
        assert [a.sources for a in en.suggested_answers if a] == [
            a.sources for a in de.suggested_answers if a
        ]
        assert not needs_translation(item, "en")


def _distinct_answers() -> FakeLLM:
    return FakeLLM(answers={f"F{n}": f"Antwort {n * 10} [1]." for n in (1, 2, 3)})


def test_a_dropped_answer_drops_only_that_translated_answer() -> None:
    items = build(_distinct_answers())
    vote_item = _by_id(items)[VOTE1]
    second = vote_item.content["de"].suggested_answers[1]
    assert second is not None

    def drop(ref: str, german: str) -> Optional[str]:
        return None if german == second.text else _english(german)

    _translate(items, edit=drop)
    en = vote_item.content["en"]
    assert [a is not None for a in en.suggested_answers] == [True, False, True]
    assert len(en.suggested_questions) == 3
    assert en.headline.startswith("EN ")


def test_a_translation_keeps_the_gaps_where_the_german_has_them() -> None:
    items = build(FakeLLM(answers={"F2": None}), votes=[vote(1)])
    _translate(items)
    vote_item = _by_id(items)[VOTE1]
    de, en = vote_item.content["de"], vote_item.content["en"]
    assert [a is None for a in en.suggested_answers] == [False, True, False]
    assert [a.sources for a in en.suggested_answers if a] == [
        a.sources for a in de.suggested_answers if a
    ]


def test_a_translated_answer_that_loses_its_citation_is_dropped() -> None:
    items = build(FakeLLM())
    debate = _by_id(items)[TOP1]
    [answer] = debate.content["de"].suggested_answers
    assert answer is not None

    def uncite(ref: str, german: str) -> str:
        return "EN no citation" if german == answer.text else _english(german)

    _translate(items, edit=uncite)
    assert debate.content["en"].suggested_answers == []
    assert debate.content["en"].key_points


# --- answers on later runs -------------------------------------------------------


def _unanswered(stored: dict[str, FeedItem], **update: Any) -> dict[str, FeedItem]:
    """The day as stored before v7: no answers, never attempted."""
    out: dict[str, FeedItem] = {}
    for item_id, item in stored.items():
        de = item.content["de"].model_copy(update={"suggested_answers": []})
        de.source_hash = content_hash(de)
        en = item.content["en"].model_copy(update={"source_hash": de.source_hash})
        out[item_id] = item.model_copy(
            update={"content": {"de": de, "en": en}, "answer_attempts": 0} | update
        )
    return out


def test_a_run_answers_stored_items_without_rebuilding_them() -> None:
    from tests.feed.test_bulk import _day, _plan, _stored_day

    stored, edition_ids = _stored_day()
    stored = _unanswered(stored)
    llm = FakeLLM()
    day, run = _day(llm, _plan(), stored, edition_ids)
    assert day is not None
    assert set(llm.calls) == {AnswerBatch}
    assert day.built == set() and run.items_built == 0
    assert day.changed == set(stored)
    for item in day.items:
        de = item.content["de"]
        assert len(de.suggested_answers) == len(de.suggested_questions)
        assert item.answer_attempts == 1
        assert item.format_version == FEED_FORMAT_VERSION
        # Only the answers are new; the translation is now stale.
        assert de.key_points == stored[item.id].content["de"].key_points
        assert needs_translation(item, "en")


def test_a_later_run_fills_only_the_gaps() -> None:
    from tests.feed.test_bulk import _day, _plan, _stored_day

    stored, edition_ids = _stored_day(FakeLLM(answers={"F2": None}))
    vote_id = "bundestag_2026-09-24_v1"
    kept = stored[vote_id].content["de"].suggested_answers
    assert kept[1] is None and stored[vote_id].answer_attempts == 1
    llm = FakeLLM(answers={"F2": "Neu [1]."})
    day, _ = _day(llm, _plan(), stored, edition_ids)
    assert day is not None
    [prompt] = _answer_prompts(llm)
    assert "[F2] Wer war dagegen?" in prompt and "[F1] Was heißt" not in prompt
    item = _by_id(day.items)[vote_id]
    answers = item.content["de"].suggested_answers
    assert answers[0] == kept[0] and answers[2] == kept[2]
    assert answers[1] is not None and answers[1].text == "Neu [1]."
    assert item.answer_attempts == 2
    assert day.changed == {vote_id}


def test_answers_stop_being_retried_after_the_last_attempt() -> None:
    from tests.feed.test_bulk import _day, _plan, _stored_day

    stored, edition_ids = _stored_day()
    stored = _unanswered(stored, answer_attempts=MAX_ANSWER_ATTEMPTS)
    llm = FakeLLM()
    day, _ = _day(llm, _plan(), stored, edition_ids)
    assert llm.calls == []
    assert day is None


def test_a_stored_debate_without_ordered_speeches_is_skipped() -> None:
    from tests.feed.test_bulk import _day, _plan, _stored_day

    stored, edition_ids = _stored_day()
    stored = _unanswered(stored)
    llm = FakeLLM()
    day, _ = _day(llm, _plan(ordered=False), stored, edition_ids)
    assert day is not None
    # Only the vote is answered; the debates wait for their protocol.
    assert len(_answer_prompts(llm)) == 1
    assert {i.id for i in day.items if i.content["de"].suggested_answers} == {VOTE1}


def test_no_stored_answers_start_once_time_is_up() -> None:
    from tests.feed.test_bulk import _day, _plan, _stored_day

    stored, edition_ids = _stored_day()
    stored = _unanswered(stored)
    llm = FakeLLM()
    _day(llm, _plan(), stored, edition_ids, out_of_time=lambda: True)
    assert llm.calls == []


# --- speech id backfill -----------------------------------------------------------


def _without_speech_ids(items: list[FeedItem]) -> dict[str, FeedItem]:
    stored: dict[str, FeedItem] = {}
    for item in items:
        if item.debate is not None:
            debate = item.debate.model_copy(update={"speech_ids": []})
            item = item.model_copy(update={"debate": debate, "format_version": "6"})
        stored[item.id] = item
    return stored


def test_a_run_gives_stored_debates_their_speech_ids_without_a_call() -> None:
    from tests.feed.test_bulk import _day, _plan, _stored_day

    stored, edition_ids = _stored_day()
    llm = FakeLLM()
    day, _ = _day(llm, _plan(), _without_speech_ids(list(stored.values())), edition_ids)
    assert day is not None
    assert llm.calls == []
    items = _by_id(day.items)
    debate = items[TOP1].debate
    assert debate is not None
    assert debate.speech_ids == ["s1", "s2", "s3"]
    assert items[TOP1].format_version == FEED_FORMAT_VERSION
    assert TOP1 in day.changed


def test_the_speech_id_backfill_writes_stored_debates_without_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _without_speech_ids(build(FakeLLM(), votes=[vote(1)]))
    sources = bulk.WindowSources(
        (date(2026, 9, 20), date(2026, 9, 24)), [vote(1)], sittings()
    )
    written: list[FeedItem] = []
    monkeypatch.setattr(bulk, "load_sources", lambda *_, **__: sources)
    monkeypatch.setattr(bulk, "read_items_since", lambda *_: list(stored.values()))
    monkeypatch.setattr(
        bulk, "write_feed", lambda _db, _editions, items: written.extend(items)
    )

    def no_model(*_: Any, **__: Any) -> Any:
        raise AssertionError("the backfill makes no LLM call")

    monkeypatch.setattr(FeedBuilder, "acall", no_model)

    assert bulk.backfill_speech_ids(object(), None, [BUNDESTAG], 14) == 2  # type: ignore[arg-type]
    assert {i.id: i.debate.speech_ids for i in written if i.debate} == {
        TOP1: ["s1", "s2", "s3"],
        "bundestag_2026-09-24_d45-top2": ["s4"],
    }
