# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import time
from datetime import date
from typing import Any, Optional

import pytest

from ingestion.feed import bulk
from ingestion.feed.builder import FeedBuilder, plan_days
from ingestion.feed.items import MAX_POSITION_ATTEMPTS
from ingestion.feed.models import FeedItem
from ingestion.feed.parliaments import FEED_PARLIAMENTS
from ingestion.feed.politicians import RefreshReport
from ingestion.feed.prompts import (
    DebateDraft,
    PositionCheckBatch,
    PositionsDraft,
    VoteEnrichmentBatch,
)
from ingestion.feed.translate import needs_translation
from tests.feed.samples import (
    BUNDESTAG,
    DISPLAY,
    NOW,
    FakeLLM,
    default_speeches,
    sittings,
    speech,
    vote,
)


def _plan(payloads: Optional[list[dict]] = None, ordered: bool = True) -> Any:
    [plan] = plan_days(BUNDESTAG, [vote(1)], sittings(payloads, ordered=ordered))
    return plan


def _day(
    llm: FakeLLM,
    plan: Any,
    stored: dict[str, FeedItem],
    stored_edition_ids: Optional[list[str]] = None,
    out_of_time: Any = lambda: False,
    lookup_poll: Any = None,
) -> tuple[Optional[bulk.DayBuild], bulk.ParliamentRun]:
    run = bulk.ParliamentRun(BUNDESTAG, None)
    builder = FeedBuilder(llm)
    try:
        day = bulk.plan_day(
            builder,
            BUNDESTAG,
            plan,
            DISPLAY,
            stored=stored,
            stored_edition_ids=stored_edition_ids,
            force=False,
            run=run,
            out_of_time=out_of_time,
            now=NOW,
            lookup_poll=lookup_poll,
        )
    finally:
        builder.close()
    return day, run


def _translated(items: list[FeedItem]) -> dict[str, FeedItem]:
    from tests.feed.test_store import _with_english

    return {i.id: _with_english(i) for i in items}


def _stored_day(llm: Optional[FakeLLM] = None) -> tuple[dict[str, FeedItem], list[str]]:
    day, _ = _day(llm or FakeLLM(), _plan(), {})
    assert day is not None
    return _translated(day.items), day.edition.item_ids


TOP1 = "bundestag_2026-09-24_d45-top1"


def _stored_without_cdu() -> tuple[dict[str, FeedItem], list[str]]:
    """The day stored with the CDU's position on TOP 1 still missing."""
    stored, edition_ids = _stored_day(FakeLLM(omit=("cdu",), retry_omit=("cdu",)))
    assert stored[TOP1].pending_positions == ["cdu"]
    return stored, edition_ids


def test_a_new_day_builds_every_item() -> None:
    day, run = _day(FakeLLM(), _plan(), {})
    assert day is not None
    assert day.edition.item_ids == [
        "bundestag_2026-09-24_d45-top1",
        "bundestag_2026-09-24_d45-top2",
        "bundestag_2026-09-24_v1",
    ]
    assert day.changed == set(day.edition.item_ids)
    assert run.items_built == 3


def test_an_unchanged_day_costs_no_call() -> None:
    stored, edition_ids = _stored_day()
    llm = FakeLLM()
    day, _ = _day(llm, _plan(), stored, edition_ids)
    assert day is None
    assert llm.calls == []


def test_a_day_stored_under_the_old_hash_costs_no_call() -> None:
    stored, edition_ids = _stored_day()
    plan = _plan()
    legacy = {u.item_id: u.legacy_input_hash for u in [*plan.debates, *plan.votes]}
    old = {
        item_id: item.model_copy(update={"input_hash": legacy[item_id]})
        for item_id, item in stored.items()
    }
    llm = FakeLLM()
    day, _ = _day(llm, plan, old, edition_ids)
    assert day is None
    assert llm.calls == []


def test_a_late_speech_rebuilds_only_its_own_debate() -> None:
    stored, edition_ids = _stored_day()
    late = default_speeches() + [
        speech("s5", speaker="Emil", party="spd", text="Nachtrag.", agenda="top2")
    ]
    llm = FakeLLM()
    day, run = _day(llm, _plan(late), stored, edition_ids)
    assert day is not None
    assert day.built == {"bundestag_2026-09-24_d45-top2"}
    assert llm.calls.count(DebateDraft) == 1
    assert VoteEnrichmentBatch not in llm.calls
    assert day.retracted_ids == []
    assert run.items_built == 1


def test_an_item_whose_source_unit_vanished_is_retracted() -> None:
    stored, edition_ids = _stored_day()
    day, _ = _day(FakeLLM(), _plan(default_speeches()[:3]), stored, edition_ids)
    assert day is not None
    assert day.retracted_ids == ["bundestag_2026-09-24_d45-top2"]
    assert "bundestag_2026-09-24_d45-top2" not in day.edition.item_ids


def test_a_debate_without_its_protocol_keeps_the_stored_version() -> None:
    stored, edition_ids = _stored_day()
    late = default_speeches() + [
        speech("s5", speaker="Emil", party="spd", text="Nachtrag.", agenda="top2")
    ]
    llm = FakeLLM()
    day, run = _day(llm, _plan(late, ordered=False), stored, edition_ids)
    assert run.deferred == 1
    assert llm.calls == []
    # Nothing changed for the reader, so nothing is written.
    assert day is None


def test_a_debate_never_built_waits_for_its_protocol() -> None:
    day, run = _day(FakeLLM(), _plan(ordered=False), {})
    assert day is not None
    assert day.edition.item_ids == ["bundestag_2026-09-24_v1"]
    assert run.deferred == 2


def test_an_older_shape_listed_by_the_stored_edition_is_retracted() -> None:
    stored, edition_ids = _stored_day()
    day, _ = _day(
        FakeLLM(), _plan(), stored, edition_ids + ["bundestag_2026-09-24_da36c6deb"]
    )
    assert day is not None
    assert day.retracted_ids == ["bundestag_2026-09-24_da36c6deb"]


def test_a_spent_budget_stops_between_days(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = default_speeches() + [
        speech(
            "x", speaker="Xaver", party="spd", text="x", day="2026-09-25", session=46
        )
    ]
    monkeypatch.setattr(
        bulk,
        "load_sources",
        lambda *_, **__: bulk.WindowSources(
            (date(2026, 9, 24), date(2026, 9, 25)), [], sittings(payloads)
        ),
    )
    monkeypatch.setattr(bulk, "load_party_display", lambda *_: DISPLAY)
    published: list[Any] = []
    calls = iter([False, False, True, True])
    builder = FeedBuilder(FakeLLM())
    try:
        run = bulk.build_for_parliament(
            None,  # type: ignore[arg-type]
            BUNDESTAG,
            builder,
            days=14,
            env="dev",
            db=None,
            force=False,
            publish_day=lambda day, _stored: published.append(day.edition.id),
            out_of_time=lambda: next(calls, True),
            now=NOW,
        )
    finally:
        builder.close()
    assert published == ["bundestag_2026-09-25"]
    assert run.out_of_time


def test_only_the_bundestag_is_built_by_default() -> None:
    assert FEED_PARLIAMENTS == ["bundestag"]


def test_a_missing_position_is_retried_alone_and_the_rest_stays_as_written() -> None:
    stored, edition_ids = _stored_without_cdu()
    llm = FakeLLM(retry_omit=("cdu",))
    day, run = _day(llm, _plan(), stored, edition_ids)
    assert day is not None
    assert llm.calls == [PositionsDraft]
    item = next(i for i in day.items if i.id == TOP1)
    assert item.content["de"] == stored[TOP1].content["de"]
    # The German text is unchanged, so the translation stands.
    assert not needs_translation(item, "en")
    assert (item.pending_positions, item.position_attempts) == (["cdu"], 2)
    assert day.changed == {TOP1}
    assert run.incomplete == 1


def test_a_position_verified_later_joins_in_party_order() -> None:
    stored, edition_ids = _stored_without_cdu()
    llm = FakeLLM()
    day, run = _day(llm, _plan(), stored, edition_ids)
    assert day is not None
    assert DebateDraft not in llm.calls
    assert llm.calls == [PositionsDraft, PositionCheckBatch]
    item = next(i for i in day.items if i.id == TOP1)
    assert item.content["de"].headline == stored[TOP1].content["de"].headline
    assert [p.party_id for p in item.content["de"].positions] == ["spd", "cdu"]
    assert item.pending_positions == []
    assert needs_translation(item, "en")
    assert run.incomplete == 0
    assert item.debate is not None
    sources = {p.party_id: p.position_sources for p in item.debate.parties}
    # The retried position keeps where it comes from: the Union's first speech.
    assert [s.speaker for s in sources["cdu"]] == ["Bernd"]


def test_a_position_that_never_verifies_stops_being_retried() -> None:
    stored, edition_ids = _stored_without_cdu()
    stored[TOP1] = stored[TOP1].model_copy(
        update={"position_attempts": MAX_POSITION_ATTEMPTS}
    )
    llm = FakeLLM()
    day, run = _day(llm, _plan(), stored, edition_ids)
    assert day is None
    assert llm.calls == []
    assert run.incomplete == 0


def test_a_failed_retry_keeps_the_stored_debate_and_its_attempts() -> None:
    stored, edition_ids = _stored_without_cdu()
    day, _ = _day(FakeLLM(fail=(PositionsDraft,)), _plan(), stored, edition_ids)
    assert day is None


def test_new_sources_rebuild_the_whole_debate_and_reset_the_attempts() -> None:
    stored, edition_ids = _stored_without_cdu()
    stored[TOP1] = stored[TOP1].model_copy(
        update={"position_attempts": MAX_POSITION_ATTEMPTS}
    )
    late = default_speeches() + [
        speech("s5", speaker="Emil", party="spd", text="Nachtrag.", agenda="top1")
    ]
    llm = FakeLLM()
    day, _ = _day(llm, _plan(late), stored, edition_ids)
    assert day is not None
    assert llm.calls.count(DebateDraft) == 1
    item = next(i for i in day.items if i.id == TOP1)
    assert (item.pending_positions, item.position_attempts) == ([], 1)


def test_a_failed_check_keeps_the_stored_debate() -> None:
    stored, edition_ids = _stored_day()
    late = default_speeches() + [
        speech("s5", speaker="Emil", party="spd", text="Nachtrag.", agenda="top2")
    ]
    llm = FakeLLM(fail=(PositionCheckBatch,))
    day, _ = _day(llm, _plan(late), stored, edition_ids)
    assert DebateDraft in llm.calls
    # Nothing was built, so the stored debate stays listed and nothing is written.
    assert day is None


def test_a_failed_vote_enrichment_keeps_the_stored_texts() -> None:
    stored, edition_ids = _stored_day()
    changed = vote(1)
    changed["content_hash"] = "vote-1-corrected"
    [plan] = plan_days(BUNDESTAG, [changed], sittings())
    day, run = _day(FakeLLM(fail=(VoteEnrichmentBatch,)), plan, stored, edition_ids)
    assert day is None
    assert run.incomplete == 1


def test_a_failed_vote_enrichment_still_shows_a_new_vote() -> None:
    day, run = _day(FakeLLM(fail=(VoteEnrichmentBatch,)), _plan(), {})
    assert day is not None
    v1 = next(i for i in day.items if i.kind == "vote")
    assert v1.content["de"].headline == "Antrag 1"
    assert run.incomplete == 1


def _plan_with_documents(
    top1: Optional[list[str]], interjections: Optional[int] = None
) -> Any:
    plan = _plan()
    plan.debates[0].agenda.drucksachen = top1
    plan.debates[0].agenda.interjections = interjections
    return plan


def test_stored_items_get_their_drucksachen_without_a_rebuild() -> None:
    stored, edition_ids = _stored_day()
    llm = FakeLLM()
    lookups: list[int] = []

    def lookup(poll_id: int) -> list[str]:
        lookups.append(poll_id)
        return ["21/6130"]

    day, _ = _day(
        llm, _plan_with_documents(["21/6130"]), stored, edition_ids, lookup_poll=lookup
    )
    assert day is not None
    assert llm.calls == []
    assert day.built == set()
    items = {i.id: i for i in day.items}
    assert items[TOP1].debate is not None
    assert items[TOP1].debate.drucksachen == ["21/6130"]
    vote_id = "bundestag_2026-09-24_v1"
    assert items[vote_id].vote is not None
    assert items[vote_id].vote.drucksachen == ["21/6130"]
    # Written, with texts and translation as they were.
    assert day.changed == {TOP1, vote_id}
    assert not needs_translation(items[TOP1], "en")
    assert lookups == [1]


def test_drucksachen_are_looked_up_once_and_retried_after_a_failure() -> None:
    stored, edition_ids = _stored_day()
    day, _ = _day(
        FakeLLM(),
        _plan_with_documents(None),
        stored,
        edition_ids,
        lookup_poll=lambda poll_id: None,
    )
    # Nothing learned: the day stays as stored, and the next run asks again.
    assert day is None

    vote_id = "bundestag_2026-09-24_v1"
    vote = stored[vote_id].vote
    assert vote is not None
    stored[vote_id] = stored[vote_id].model_copy(
        update={"vote": vote.model_copy(update={"drucksachen": []})}
    )

    def never(poll_id: int) -> list[str]:
        raise AssertionError("a poll with an answer is not looked up again")

    assert _day(FakeLLM(), _plan(), stored, edition_ids, lookup_poll=never)[0] is None


def test_stored_debates_get_their_interjections_without_a_rebuild() -> None:
    stored, edition_ids = _stored_day()
    llm = FakeLLM()
    day, _ = _day(
        llm, _plan_with_documents(None, interjections=42), stored, edition_ids
    )
    assert day is not None
    assert llm.calls == []
    item = next(i for i in day.items if i.id == TOP1)
    assert item.debate is not None
    assert item.debate.interjections == 42
    assert day.changed == {TOP1}


def test_stored_debates_learn_who_their_speakers_are_without_a_rebuild() -> None:
    stored, edition_ids = _stored_day()
    plan = _plan()
    for spoken in plan.debates[0].agenda.speeches:
        spoken.mdb_id = f"mdb-{spoken.speaker}"
        spoken.duration = 125.4
    llm = FakeLLM()
    day, _ = _day(llm, plan, stored, edition_ids)
    assert day is not None
    assert llm.calls == []
    assert day.changed == {TOP1}
    item = next(i for i in day.items if i.id == TOP1)
    assert item.debate is not None
    speakers = [s for p in item.debate.parties for s in p.speakers]
    assert {(s.name, s.mdb_id, s.duration) for s in speakers} == {
        ("Anna", "mdb-Anna", 125),
        ("Bernd", "mdb-Bernd", 125),
        ("Clara", "mdb-Clara", 125),
    }
    # Texts and translation stay as they were.
    assert item.content == stored[TOP1].content
    assert not needs_translation(item, "en")


def test_a_run_without_speaker_ids_never_clears_stored_ones() -> None:
    stored, edition_ids = _stored_day()
    plan = _plan()
    for spoken in plan.debates[0].agenda.speeches:
        spoken.mdb_id = f"mdb-{spoken.speaker}"
    day, _ = _day(FakeLLM(), plan, stored, edition_ids)
    assert day is not None
    stored = {i.id: i for i in day.items}
    # A run whose protocol could not be read knows no ids.
    assert _day(FakeLLM(), _plan(), stored, edition_ids)[0] is None


TOP2 = "bundestag_2026-09-24_d45-top2"


def _failed(
    llm: Any,
    plan: Any,
    stored: Optional[dict[str, FeedItem]] = None,
    stored_edition_ids: Optional[list[str]] = None,
    deadline: Optional[float] = None,
) -> list[str]:
    builder = FeedBuilder(llm, deadline=deadline)
    try:
        bulk.plan_day(
            builder,
            BUNDESTAG,
            plan,
            DISPLAY,
            stored=stored or {},
            stored_edition_ids=stored_edition_ids,
            force=False,
            run=bulk.ParliamentRun(BUNDESTAG, None),
            out_of_time=lambda: False,
            now=NOW,
        )
    finally:
        builder.close()
    return builder.failed


def test_a_debate_whose_call_raised_is_recorded_as_failed() -> None:
    assert sorted(_failed(FakeLLM(fail=(DebateDraft,)), _plan())) == [TOP1, TOP2]


def test_a_failed_position_retry_is_recorded_as_failed() -> None:
    stored, edition_ids = _stored_without_cdu()
    llm = FakeLLM(fail=(PositionsDraft,))
    assert _failed(llm, _plan(), stored, edition_ids) == [TOP1]


def test_a_failed_vote_enrichment_is_recorded_as_failed() -> None:
    assert _failed(FakeLLM(fail=(VoteEnrichmentBatch,)), _plan()) == ["poll 1"]


def test_a_call_the_time_budget_cut_is_not_a_failure() -> None:
    assert _failed(FakeLLM(), _plan(), deadline=time.monotonic() - 1) == []


def _main(
    monkeypatch: pytest.MonkeyPatch,
    runs: list[Any],
    written: Optional[list[str]] = None,
) -> tuple[int, list[str]]:
    written = written or []
    revalidated: list[str] = []
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setattr(bulk, "guard_firestore_target", lambda *_, **__: None)
    monkeypatch.setattr(bulk, "_firestore_client", lambda: object())
    monkeypatch.setattr(bulk, "check_fingerprint", lambda *_: None)
    monkeypatch.setattr(bulk, "refresh_calendar", lambda *_: None)
    monkeypatch.setattr(
        bulk, "refresh_speakers", lambda *_, **__: RefreshReport(written=written)
    )
    monkeypatch.setattr(bulk, "build_and_publish", lambda *_, **__: runs)
    monkeypatch.setattr(bulk, "post_revalidate", revalidated.append)
    return bulk.main(["--revalidate", "--allow-remote"]), revalidated


WINDOW = (date(2026, 9, 24), date(2026, 9, 24))


def test_a_run_that_wrote_busts_the_web_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [(bulk.ParliamentRun(BUNDESTAG, WINDOW), bulk.Published(retracted=1))]
    assert _main(monkeypatch, runs) == (0, ["dev"])


def test_a_run_that_wrote_nothing_leaves_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [(bulk.ParliamentRun(BUNDESTAG, WINDOW), bulk.Published())]
    assert _main(monkeypatch, runs) == (0, [])


def test_a_run_that_only_stored_politicians_busts_the_web_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [(bulk.ParliamentRun(BUNDESTAG, WINDOW), bulk.Published())]
    assert _main(monkeypatch, runs, written=["11005000"]) == (0, ["dev"])


def test_a_failed_item_fails_the_run_after_publishing_the_rest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run = bulk.ParliamentRun(BUNDESTAG, WINDOW, failed=[TOP1])
    runs = [(run, bulk.Published(retracted=1))]
    assert _main(monkeypatch, runs) == (1, ["dev"])
    assert TOP1 in capsys.readouterr().err


class _Response:
    def raise_for_status(self) -> None:
        pass


def _revalidate_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    sent: dict[str, str] = {}

    def post(url: str, **kwargs: Any) -> _Response:
        sent.update(kwargs["headers"])
        return _Response()

    monkeypatch.setenv("REVALIDATE_SECRET", "secret")
    monkeypatch.setattr(bulk.httpx, "post", post)
    bulk.post_revalidate("dev")
    return sent


def test_revalidation_passes_vercel_protection_with_the_bypass_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERCEL_AUTOMATION_BYPASS_SECRET", "bypass")
    headers = _revalidate_headers(monkeypatch)
    assert headers["x-vercel-protection-bypass"] == "bypass"
    assert headers["Authorization"] == "Bearer secret"


def test_revalidation_sends_no_bypass_header_without_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VERCEL_AUTOMATION_BYPASS_SECRET", raising=False)
    assert "x-vercel-protection-bypass" not in _revalidate_headers(monkeypatch)
