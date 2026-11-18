# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from ingestion.feed import bulk
from ingestion.feed.calendar import (
    AGENDA_URL,
    CALENDAR_INDEX_URL,
    CalendarError,
    build_calendar,
    parse_german_date,
    parse_sitting_weeks,
)
from ingestion.feed.models import SittingWeek

INDEX_HTML = """
<a href="/parlament/plenum/sitzungskalender/bt2026-1084980">2026</a>
<a href="/parlament/plenum/sitzungskalender/bt2027-1158140">2027</a>
<a href="https://example.org/parlament/plenum/sitzungskalender/bt2028-1">x</a>
"""
YEAR_2026 = "https://www.bundestag.de/parlament/plenum/sitzungskalender/bt2026-1084980"
YEAR_2027 = "https://www.bundestag.de/parlament/plenum/sitzungskalender/bt2027-1158140"

# Shaped like the real page: the meta description repeats the first ranges
# and cuts off mid-range.
PAGE_2026 = """
<meta name="description" content="Januar 12.01. - 16.01.2026 26.01. - 30.01.2026
Juli 06.07. - 10.07.20..."/>
<h2>Januar</h2><p>12.01. - 16.01.2026<br />26.01. - 30.01.2026</p>
<h2>Februar</h2><p>23.02. - 27.02.2026</p>
<h2>März</h2><p>02.03. - 06.03.2026<br />16.03. - 20.03.2026<br />23.03. - 27.03.2026</p>
<h2>April</h2><p>13.04. - 17.04.2026<br />20.04. - 24.04.2026</p>
<h2>Oktober</h2><p>05.10. - 09.10.2026<br />12.10. - 16.10.2026</p>
<h2>November</h2><p>02.11. - 06.11.2026<br />09.11. - 13.11.2026<br />23.11. - 27.11.2026</p>
<h2>Dezember</h2><p>07.12. - 11.12.2026<br />14.12. - 18.12.2026</p>
"""
PAGE_2027 = "".join(
    f"<p>{d:02d}.0{m}. - {d + 4:02d}.0{m}.2027</p>"
    for m in range(1, 7)
    for d in (11, 18)
)


def _agenda(conferences: list[tuple[int, str]], **links: Any) -> str:
    return json.dumps(
        {
            **links,
            "conferences": [
                {
                    "conferenceNumber": number,
                    "conferenceDate": {"date": day},
                    "rows": [],
                }
                for number, day in conferences
            ],
        }
    )


WEEK_45 = _agenda(
    [(104, "4. November 2026"), (105, "5. November 2026"), (106, "6. November 2026")],
    previous={"week": 42, "year": 2026},
)
WEEK_41 = _agenda(
    [(98, "7. Oktober 2026"), (99, "8. Oktober 2026"), (100, "9. Oktober 2026")]
)
WEEK_42 = _agenda(
    [(101, "14. Oktober 2026"), (102, "15. Oktober 2026"), (103, "16. Oktober 2026")]
)


def _week(number: int) -> str:
    return f"{AGENDA_URL}?year=2026&week={number}"


def _fetcher(pages: dict[str, str], asked: list[str] | None = None) -> Any:
    def fetch(url: str) -> str:
        if asked is not None:
            asked.append(url)
        if url not in pages:
            raise ConnectionError(url)
        return pages[url]

    return fetch


ALL_UP = {
    CALENDAR_INDEX_URL: INDEX_HTML,
    YEAR_2026: PAGE_2026,
    YEAR_2027: PAGE_2027,
    AGENDA_URL: WEEK_45,
    _week(41): WEEK_41,
    _week(42): WEEK_42,
    _week(45): WEEK_45,
}
NOW = datetime(2026, 11, 4, 5, tzinfo=timezone.utc)


def _days(week: SittingWeek) -> list[tuple[date, int]]:
    return [(s.date, s.number) for s in week.sittings or []]


def test_year_page_ranges_are_deduped_and_ordered() -> None:
    weeks = parse_sitting_weeks(PAGE_2026)
    assert len(weeks) == 15
    assert weeks[0] == (date(2026, 1, 12), date(2026, 1, 16))
    assert weeks[-1] == (date(2026, 12, 14), date(2026, 12, 18))


def test_a_week_across_new_year_starts_in_the_old_year() -> None:
    assert parse_sitting_weeks("<p>29.12. - 02.01.2027</p>") == [
        (date(2026, 12, 29), date(2027, 1, 2))
    ]


def test_german_dates() -> None:
    assert parse_german_date("4. November 2026") == date(2026, 11, 4)
    assert parse_german_date("2. März 2027") == date(2027, 3, 2)
    with pytest.raises(ValueError):
        parse_german_date("4. Brumaire 2026")


def test_the_calendar_reaches_back_to_the_feeds_start_with_exact_days() -> None:
    calendar = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)
    assert calendar.since == date(2026, 9, 1)
    # January to April are before the feed: left out.
    assert calendar.weeks[0].start == date(2026, 10, 5)
    october, october_2, november = calendar.weeks[:3]
    assert _days(october)[0] == (date(2026, 10, 7), 98)
    assert _days(october_2)[-1] == (date(2026, 10, 16), 103)
    assert (november.start, november.end) == (date(2026, 11, 2), date(2026, 11, 6))
    assert _days(november) == [
        (date(2026, 11, 4), 104),
        (date(2026, 11, 5), 105),
        (date(2026, 11, 6), 106),
    ]
    assert (calendar.weeks[3].start, calendar.weeks[3].sittings) == (
        date(2026, 11, 9),
        None,
    )
    assert calendar.sources == [CALENDAR_INDEX_URL, AGENDA_URL]


def test_weeks_ahead_stop_after_upcoming_weeks_including_next_year() -> None:
    calendar = build_calendar(date(2026, 12, 12), _fetcher(ALL_UP), now=NOW)
    ahead = [w for w in calendar.weeks if w.end >= date(2026, 12, 12)]
    assert ahead[0].start == date(2026, 12, 14)
    assert ahead[1].start == date(2027, 1, 11)
    assert len(ahead) == 6
    # The past since the feed began stays.
    assert calendar.weeks[0].start == date(2026, 10, 5)


def test_agenda_follows_next_links() -> None:
    pages = {
        **ALL_UP,
        AGENDA_URL: _agenda(
            [(104, "4. November 2026")], next={"week": 46, "year": 2026}
        ),
        _week(46): _agenda([(107, "11. November 2026")]),
    }
    calendar = build_calendar(date(2026, 11, 7), _fetcher(pages), now=NOW)
    week_46 = next(w for w in calendar.weeks if w.start == date(2026, 11, 9))
    assert _days(week_46) == [(date(2026, 11, 11), 107)]


def test_special_sittings_outside_the_calendar_form_one_week() -> None:
    pages = {
        **ALL_UP,
        AGENDA_URL: _agenda([(107, "21. Oktober 2026"), (108, "22. Oktober 2026")]),
    }
    calendar = build_calendar(date(2026, 10, 19), _fetcher(pages), now=NOW)
    special = next(w for w in calendar.weeks if w.start == date(2026, 10, 21))
    assert special.end == date(2026, 10, 22)
    assert [n for _, n in _days(special)] == [107, 108]


def test_weeks_too_far_ahead_are_not_asked_for() -> None:
    asked: list[str] = []
    calendar = build_calendar(
        date(2026, 10, 20), _fetcher({**ALL_UP, AGENDA_URL: _agenda([])}, asked)
    )
    later = next(w for w in calendar.weeks if w.start == date(2026, 11, 9))
    assert later.sittings is None
    assert _week(46) not in asked


def test_settled_days_are_reused_without_asking_again() -> None:
    stored = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)
    asked: list[str] = []
    pages = {k: v for k, v in ALL_UP.items() if k not in (_week(41), _week(42))}
    calendar = build_calendar(
        date(2026, 11, 20), _fetcher(pages, asked), now=NOW, stored=stored
    )
    assert _week(41) not in asked and _week(42) not in asked
    assert _days(calendar.weeks[0])[0] == (date(2026, 10, 7), 98)


def test_a_recent_week_is_asked_again_and_a_failure_keeps_its_days() -> None:
    stored = build_calendar(
        date(2026, 11, 4),
        _fetcher({**ALL_UP, _week(45): _agenda([(104, "4. November 2026")])}),
        now=NOW,
        stored=None,
    )
    # A week that ended days ago may still change: asked again.
    fresh = build_calendar(date(2026, 11, 10), _fetcher(ALL_UP), stored=stored)
    november = next(w for w in fresh.weeks if w.start == date(2026, 11, 2))
    assert len(_days(november)) == 3
    # Its agenda failing keeps what was stored.
    failing = {k: v for k, v in ALL_UP.items() if k not in (_week(45), AGENDA_URL)}
    kept = build_calendar(date(2026, 11, 10), _fetcher(failing), stored=fresh)
    november = next(w for w in kept.weeks if w.start == date(2026, 11, 2))
    assert len(_days(november)) == 3


def test_stored_weeks_outlive_a_year_page_the_index_drops() -> None:
    stored = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)
    pages = {
        CALENDAR_INDEX_URL: '<a href="/parlament/plenum/sitzungskalender/bt2027-1158140">',
        YEAR_2027: PAGE_2027,
        AGENDA_URL: _agenda([]),
    }
    calendar = build_calendar(date(2027, 3, 1), _fetcher(pages), stored=stored)
    assert calendar.weeks[0].start == date(2026, 10, 5)
    assert _days(calendar.weeks[0])[0] == (date(2026, 10, 7), 98)


def test_either_source_alone_is_enough() -> None:
    no_agenda = {
        k: v
        for k, v in ALL_UP.items()
        if k not in (AGENDA_URL, _week(41), _week(42), _week(45))
    }
    assert build_calendar(date(2026, 11, 4), _fetcher(no_agenda)).sources == [
        CALENDAR_INDEX_URL
    ]
    agenda_only = {AGENDA_URL: WEEK_45}
    calendar = build_calendar(date(2026, 11, 4), _fetcher(agenda_only))
    assert calendar.sources == [AGENDA_URL]
    # The agenda's days form one week, not one per day.
    assert [(w.start, w.end) for w in calendar.weeks] == [
        (date(2026, 11, 4), date(2026, 11, 6))
    ]


def test_a_year_page_with_too_few_weeks_is_not_trusted() -> None:
    pages = {**ALL_UP, YEAR_2026: "<p>12.01. - 16.01.2026</p>"}
    calendar = build_calendar(date(2026, 11, 4), _fetcher(pages), now=NOW)
    # The calendar is dropped as a whole; the agenda still answers.
    assert calendar.sources == [AGENDA_URL]


def test_an_index_without_this_years_page_is_not_trusted() -> None:
    pages = {**ALL_UP, CALENDAR_INDEX_URL: "<p>moved</p>"}
    assert build_calendar(date(2026, 11, 4), _fetcher(pages)).sources == [AGENDA_URL]


def test_no_answer_at_all_raises() -> None:
    with pytest.raises(CalendarError):
        build_calendar(date(2026, 11, 4), _fetcher({}))


class _CalendarDb:
    def __init__(self, stored: dict | None = None) -> None:
        self.stored = stored
        self.written: dict[tuple[str, str], dict] = {}

    def collection(self, name: str) -> Any:
        def document(doc_id: str) -> Any:
            return SimpleNamespace(
                set=lambda data: self.written.__setitem__((name, doc_id), data),
                get=lambda: SimpleNamespace(
                    exists=self.stored is not None, to_dict=lambda: self.stored
                ),
            )

        return SimpleNamespace(document=document)


def test_refresh_builds_on_the_stored_copy_and_writes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)
    seen: list[Any] = []

    def build(today: date, stored: Any = None) -> Any:
        seen.append(stored)
        return previous

    monkeypatch.setattr(bulk, "build_calendar", build)
    db = _CalendarDb(previous.model_dump(mode="json"))
    bulk.refresh_calendar(db, now=NOW + timedelta(days=1))
    assert seen[0] is not None and seen[0].since == date(2026, 9, 1)
    stored = db.written[("feed_calendar", "bundestag")]
    november = next(w for w in stored["weeks"] if w["start"] == "2026-11-02")
    assert november["sittings"][0] == {"date": "2026-11-04", "number": 104}


def test_refresh_keeps_the_stored_copy_when_nothing_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(today: date, stored: Any = None) -> Any:
        raise CalendarError("down")

    monkeypatch.setattr(bulk, "build_calendar", unavailable)
    db = _CalendarDb()
    bulk.refresh_calendar(db)
    assert db.written == {}


def test_refresh_leaves_a_copy_checked_today(monkeypatch: pytest.MonkeyPatch) -> None:
    # The job runs several times a night; only the first one asks bundestag.de.
    previous = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)

    def build(today: date, stored: Any = None) -> Any:
        raise AssertionError("a fresh calendar is not rebuilt")

    monkeypatch.setattr(bulk, "build_calendar", build)
    db = _CalendarDb(previous.model_dump(mode="json"))
    bulk.refresh_calendar(db, now=NOW + timedelta(hours=2))
    assert db.written == {}
