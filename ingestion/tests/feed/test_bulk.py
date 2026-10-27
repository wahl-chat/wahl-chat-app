# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from typing import Any

import pytest

from ingestion.feed import bulk
from ingestion.feed.parliaments import PARLIAMENTS


def _run_with(
    monkeypatch: pytest.MonkeyPatch, days: list[Any], out_of_time: Any
) -> tuple[bulk.ParliamentRun, list[Any]]:
    monkeypatch.setattr(
        bulk, "parliament_window", lambda *_: (date(2026, 9, 1), date(2026, 9, 25))
    )
    monkeypatch.setattr(bulk, "scroll_payloads", lambda *_: [])
    monkeypatch.setattr(bulk, "load_party_display", lambda *_: {})
    monkeypatch.setattr(bulk, "iter_digests", lambda *_, **__: iter(days))
    published: list[Any] = []
    run = bulk.build_for_parliament(
        None,  # type: ignore[arg-type]
        PARLIAMENTS["landtag_st"],
        None,  # type: ignore[arg-type]
        days=14,
        env="dev",
        existing_hashes={},
        force=False,
        publish_day=published.append,
        out_of_time=out_of_time,
    )
    return run, published


def test_each_day_is_published_as_soon_as_it_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, published = _run_with(monkeypatch, [None, "day-2", "day-1"], lambda: False)
    assert published == ["day-2", "day-1"]
    assert (run.unchanged, run.out_of_time) == (1, False)


def test_a_spent_budget_stops_between_days(monkeypatch: pytest.MonkeyPatch) -> None:
    run, published = _run_with(monkeypatch, [None, "day-2", "day-1"], lambda: True)
    assert published == ["day-2"]
    assert run.out_of_time
