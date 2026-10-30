# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from typing import Any, Optional

import pytest

from ingestion.feed import bulk
from ingestion.feed.builder import FeedBuilder, plan_days
from ingestion.feed.models import FeedItem
from ingestion.feed.parliaments import FEED_PARLIAMENTS
from ingestion.feed.prompts import DebateDraft, VoteEnrichmentBatch
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
        )
    finally:
        builder.close()
    return day, run


def _translated(items: list[FeedItem]) -> dict[str, FeedItem]:
    from tests.feed.test_store import _with_english

    return {i.id: _with_english(i) for i in items}


def _stored_day() -> tuple[dict[str, FeedItem], list[str]]:
    day, _ = _day(FakeLLM(), _plan(), {})
    assert day is not None
    return _translated(day.items), day.edition.item_ids


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
