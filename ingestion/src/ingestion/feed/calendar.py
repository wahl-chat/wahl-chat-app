# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""When the Bundestag sits next, from two official bundestag.de sources.

DIP has no calendar: it lists a sitting's protocol only a day ahead. The
Bundestag publishes the rest:

- the yearly Sitzungskalender page, which lists every sitting week months
  ahead but not which days of it have plenary sittings;
- the JSON behind bundestag.de/tagesordnung, which has the exact plenary days
  of a week once its agenda is published, about a week ahead. Special
  sittings outside the calendar's weeks appear only there.

Each source is used when it answers. Weeks come from the calendar, and the
agenda adds the days it knows and any week the calendar lacks.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any, Optional

from ingestion.connectors.bundestag_speeches.client import fetch_text
from ingestion.feed.models import PlenarySitting, SittingCalendar, SittingWeek

logger = logging.getLogger(__name__)

Fetch = Callable[[str], str]

SITE = "https://www.bundestag.de"
CALENDAR_INDEX_URL = f"{SITE}/parlament/plenum/sitzungskalender"
AGENDA_URL = f"{SITE}/apps/plenar/plenar/conferenceWeekJSON"

# Year pages are linked from the index as ``…/sitzungskalender/bt2026-1084980``;
# only the path is taken, so a link elsewhere is never followed.
_YEAR_PAGE = re.compile(r"/parlament/plenum/sitzungskalender/bt(\d{4})-(\d+)")
# "12.01. - 16.01.2026". The page's meta description repeats the ranges, and
# cuts off its last one without a full year, so it never adds a wrong week.
_WEEK_RANGE = re.compile(r"(\d{2})\.(\d{2})\. - (\d{2})\.(\d{2})\.(\d{4})")
# The Bundestag sits about 20 weeks a year; a page yielding far fewer has
# changed its markup, and publishing from it would hide real weeks.
MIN_WEEKS_PER_YEAR = 10
_GERMAN_DATE = re.compile(r"(\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})")
_MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember",
        ],
        start=1,
    )
}
# The agenda links week to week; a published agenda is never more than a few
# weeks ahead, so this only stops a link cycle.
_MAX_AGENDA_WEEKS = 4
UPCOMING_WEEKS = 6


class CalendarError(Exception):
    """Neither source yielded a usable calendar."""


def year_page_urls(index_html: str, years: set[int]) -> dict[int, str]:
    return {
        int(year): f"{SITE}/parlament/plenum/sitzungskalender/bt{year}-{page_id}"
        for year, page_id in _YEAR_PAGE.findall(index_html)
        if int(year) in years
    }


def parse_sitting_weeks(html: str) -> list[tuple[date, date]]:
    """The ``DD.MM. - DD.MM.YYYY`` ranges of a year page, in order."""
    weeks = set()
    for start_day, start_month, end_day, end_month, year in _WEEK_RANGE.findall(html):
        end = date(int(year), int(end_month), int(end_day))
        # A week spanning New Year carries only the end's year.
        start_year = end.year - 1 if int(start_month) > end.month else end.year
        weeks.add((date(start_year, int(start_month), int(start_day)), end))
    return sorted(weeks)


def parse_german_date(text: str) -> date:
    match = _GERMAN_DATE.search(text)
    if not match or match.group(2) not in _MONTHS:
        raise ValueError(f"not a German date: {text!r}")
    day, month, year = match.groups()
    return date(int(year), _MONTHS[month], int(day))


def parse_agenda(payload: dict[str, Any]) -> list[PlenarySitting]:
    return [
        PlenarySitting(
            date=parse_german_date(conference["conferenceDate"]["date"]),
            number=int(conference["conferenceNumber"]),
        )
        for conference in payload.get("conferences") or []
    ]


def sitting_weeks(fetch: Fetch, year: int) -> list[tuple[date, date]]:
    """Every sitting week of ``year`` and, once its page is out, the next."""
    pages = year_page_urls(fetch(CALENDAR_INDEX_URL), {year, year + 1})
    if year not in pages:
        raise CalendarError(f"{CALENDAR_INDEX_URL} links no page for {year}")
    weeks: list[tuple[date, date]] = []
    for year, url in sorted(pages.items()):
        found = parse_sitting_weeks(fetch(url))
        if len(found) < MIN_WEEKS_PER_YEAR:
            raise CalendarError(
                f"{url} lists {len(found)} sitting weeks, expected at least "
                f"{MIN_WEEKS_PER_YEAR}"
            )
        weeks.extend(found)
    return weeks


def plenary_sittings(fetch: Fetch) -> list[PlenarySitting]:
    """The sittings of the latest published agenda week and any after it."""
    payload = json.loads(fetch(AGENDA_URL))
    sittings = parse_agenda(payload)
    for _ in range(_MAX_AGENDA_WEEKS):
        following = payload.get("next")
        if not following:
            break
        payload = json.loads(
            fetch(f"{AGENDA_URL}?year={following['year']}&week={following['week']}")
        )
        sittings.extend(parse_agenda(payload))
    return sittings


def merge(
    weeks: list[tuple[date, date]], sittings: list[PlenarySitting]
) -> list[SittingWeek]:
    """Calendar weeks with the agenda's days in them; an agenda day outside
    every calendar week (a special sitting) becomes a week of its own."""
    merged = [SittingWeek(start=start, end=end) for start, end in weeks]
    for sitting in sittings:
        week = next((w for w in merged if w.start <= sitting.date <= w.end), None)
        if week is None:
            week = SittingWeek(start=sitting.date, end=sitting.date)
            merged.append(week)
        week.start = min(week.start, sitting.date)
        week.end = max(week.end, sitting.date)
        week.sittings = sorted(
            {s.date: s for s in [*(week.sittings or []), sitting]}.values(),
            key=lambda s: s.date,
        )
    return sorted(merged, key=lambda w: w.start)


def build_calendar(
    today: date,
    fetch: Fetch = fetch_text,
    now: Optional[datetime] = None,
) -> SittingCalendar:
    """The next ``UPCOMING_WEEKS`` sitting weeks from ``today``.

    Raises CalendarError when neither source answers, so the caller keeps the
    copy it has rather than replacing it with nothing.
    """
    sources: list[str] = []
    weeks: list[tuple[date, date]] = []
    sittings: list[PlenarySitting] = []
    try:
        weeks = sitting_weeks(fetch, today.year)
        sources.append(CALENDAR_INDEX_URL)
    except Exception as exc:  # noqa: BLE001 — the agenda may still answer
        logger.warning("Sitzungskalender unavailable: %s", exc)
    try:
        sittings = plenary_sittings(fetch)
        sources.append(AGENDA_URL)
    except Exception as exc:  # noqa: BLE001 — the calendar may still answer
        logger.warning("Bundestag agenda unavailable: %s", exc)
    if not sources:
        raise CalendarError("neither the Sitzungskalender nor the agenda answered")

    upcoming = [w for w in merge(weeks, sittings) if w.end >= today]
    return SittingCalendar(
        parliament="bundestag",
        weeks=upcoming[:UPCOMING_WEEKS],
        sources=sources,
        checked_at=now or datetime.now(timezone.utc),
    )
