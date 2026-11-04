# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from datetime import date, datetime, timezone
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


def _fetcher(pages: dict[str, str]) -> Any:
    def fetch(url: str) -> str:
        if url not in pages:
            raise ConnectionError(url)
        return pages[url]

    return fetch


ALL_UP = {
    CALENDAR_INDEX_URL: INDEX_HTML,
    YEAR_2026: PAGE_2026,
    YEAR_2027: PAGE_2027,
    AGENDA_URL: WEEK_45,
}
NOW = datetime(2026, 11, 4, 5, tzinfo=timezone.utc)


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


def test_agenda_days_fill_their_calendar_week() -> None:
    calendar = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)
    first, second = calendar.weeks[:2]
    assert (first.start, first.end) == (date(2026, 11, 2), date(2026, 11, 6))
    assert [(s.date, s.number) for s in first.sittings or []] == [
        (date(2026, 11, 4), 104),
        (date(2026, 11, 5), 105),
        (date(2026, 11, 6), 106),
    ]
    assert (second.start, second.sittings) == (date(2026, 11, 9), None)
    assert calendar.sources == [CALENDAR_INDEX_URL, AGENDA_URL]


def test_only_weeks_not_yet_over_are_kept_including_next_year() -> None:
    calendar = build_calendar(date(2026, 12, 12), _fetcher(ALL_UP), now=NOW)
    assert calendar.weeks[0].start == date(2026, 12, 14)
    assert calendar.weeks[1].start == date(2027, 1, 11)
    assert len(calendar.weeks) == 6


def test_agenda_follows_next_links() -> None:
    pages = {
        **ALL_UP,
        AGENDA_URL: _agenda(
            [(104, "4. November 2026")], next={"week": 46, "year": 2026}
        ),
        f"{AGENDA_URL}?year=2026&week=46": _agenda([(107, "11. November 2026")]),
    }
    calendar = build_calendar(date(2026, 11, 7), _fetcher(pages), now=NOW)
    assert calendar.weeks[0].sittings is not None
    assert calendar.weeks[0].sittings[0].number == 107


def test_a_special_sitting_outside_the_calendar_gets_its_own_week() -> None:
    pages = {**ALL_UP, AGENDA_URL: _agenda([(107, "21. Oktober 2026")])}
    calendar = build_calendar(date(2026, 10, 19), _fetcher(pages), now=NOW)
    first = calendar.weeks[0]
    assert (first.start, first.end) == (date(2026, 10, 21), date(2026, 10, 21))


def test_recess_agenda_leaves_weeks_without_days() -> None:
    pages = {**ALL_UP, AGENDA_URL: _agenda([])}
    calendar = build_calendar(date(2026, 10, 20), _fetcher(pages), now=NOW)
    assert calendar.weeks[0].start == date(2026, 11, 2)
    assert all(w.sittings is None for w in calendar.weeks)


def test_either_source_alone_is_enough() -> None:
    no_agenda = {k: v for k, v in ALL_UP.items() if k != AGENDA_URL}
    assert build_calendar(date(2026, 11, 4), _fetcher(no_agenda)).sources == [
        CALENDAR_INDEX_URL
    ]
    agenda_only = {AGENDA_URL: WEEK_45}
    calendar = build_calendar(date(2026, 11, 4), _fetcher(agenda_only))
    assert calendar.sources == [AGENDA_URL]
    assert calendar.weeks[0].start == date(2026, 11, 4)


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
    def __init__(self) -> None:
        self.written: dict[tuple[str, str], dict] = {}

    def collection(self, name: str) -> Any:
        def document(doc_id: str) -> Any:
            return SimpleNamespace(
                set=lambda data: self.written.__setitem__((name, doc_id), data)
            )

        return SimpleNamespace(document=document)


def test_refresh_writes_the_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    calendar = build_calendar(date(2026, 11, 4), _fetcher(ALL_UP), now=NOW)
    monkeypatch.setattr(bulk, "build_calendar", lambda today: calendar)
    db = _CalendarDb()
    bulk.refresh_calendar(db)
    stored = db.written[("feed_calendar", "bundestag")]
    assert stored["weeks"][0]["sittings"][0] == {"date": "2026-11-04", "number": 104}


def test_refresh_keeps_the_stored_copy_when_nothing_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(today: date) -> Any:
        raise CalendarError("down")

    monkeypatch.setattr(bulk, "build_calendar", unavailable)
    db = _CalendarDb()
    bulk.refresh_calendar(db)
    assert db.written == {}
