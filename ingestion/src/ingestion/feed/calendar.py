# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The Bundestag's sitting days, from two official bundestag.de sources.

DIP has no calendar: it lists a sitting's protocol only a day ahead. The
Bundestag publishes the rest:

- the yearly Sitzungskalender page, which lists every sitting week months
  ahead but not which days of it have plenary sittings;
- the JSON behind bundestag.de/tagesordnung, which has the exact plenary days
  of a week: for any past week, and for a coming one once its agenda is
  published, about a week ahead. Special sittings outside the calendar's
  weeks appear only there.

Each source is used when it answers. Weeks come from the calendar, and the
agenda adds the days it knows and any week the calendar lacks. The stored
calendar reaches back to when the feed begins, so the page can show which
sitting days have content; days already known are kept rather than fetched
again, so the past costs nothing night after night.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from ingestion.connectors.bundestag_speeches.client import fetch_text
from ingestion.feed.models import PlenarySitting, SittingCalendar, SittingWeek
from ingestion.feed.parliaments import FEED_START

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
# A week's agenda is asked for once it may be published, and again while its
# days may still change: a sitting can be added or moved at short notice.
_AGENDA_LEAD = timedelta(days=14)
_SETTLED_AFTER = timedelta(days=14)
# The feed job runs several times a night; one refresh a day is enough, and
# the job's time cap leaves no room to wait on a slow bundestag.de.
FRESH_FOR = timedelta(hours=20)
_FETCH_TIMEOUT_S = 15


def fetch_page(url: str) -> str:
    return fetch_text(url, timeout=_FETCH_TIMEOUT_S)


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


def sitting_weeks(fetch: Fetch, today: date, since: date) -> list[tuple[date, date]]:
    """Every sitting week from ``since``'s year to next year, as far as the
    index still links the year pages. This year's must be there."""
    years = set(range(since.year, today.year + 2))
    pages = year_page_urls(fetch(CALENDAR_INDEX_URL), years)
    if today.year not in pages:
        raise CalendarError(f"{CALENDAR_INDEX_URL} links no page for {today.year}")
    weeks: list[tuple[date, date]] = []
    for _, url in sorted(pages.items()):
        found = parse_sitting_weeks(fetch(url))
        if len(found) < MIN_WEEKS_PER_YEAR:
            raise CalendarError(
                f"{url} lists {len(found)} sitting weeks, expected at least "
                f"{MIN_WEEKS_PER_YEAR}"
            )
        weeks.extend(found)
    return weeks


def iso_week(day: date) -> tuple[int, int]:
    """The key a week is known by: the calendar's weeks and the agenda's both
    run Monday to Friday, and a sitting belongs to the week it falls in."""
    iso = day.isocalendar()
    return (iso.year, iso.week)


def week_agenda_url(day: date) -> str:
    year, week = iso_week(day)
    return f"{AGENDA_URL}?year={year}&week={week}"


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


def week_sittings(
    fetch: Fetch,
    weeks: list[tuple[date, date]],
    today: date,
    stored: Optional[SittingCalendar],
) -> tuple[list[PlenarySitting], bool]:
    """Each week's days: kept from the stored copy once settled, else asked
    of that week's agenda. Returns the days and whether any agenda answered.
    A week whose agenda fails keeps what the stored copy has."""
    known = {
        iso_week(w.start): w.sittings
        for w in (stored.weeks if stored else [])
        if w.sittings
    }
    sittings: list[PlenarySitting] = []
    answered = False
    for start, end in weeks:
        kept = known.get(iso_week(start))
        if kept is not None and end < today - _SETTLED_AFTER:
            sittings.extend(kept)
            continue
        if start > today + _AGENDA_LEAD:
            continue
        try:
            sittings.extend(parse_agenda(json.loads(fetch(week_agenda_url(start)))))
            answered = True
        except Exception as exc:  # noqa: BLE001 — one week, not the calendar
            logger.warning("No agenda for the week of %s: %s", start, exc)
            sittings.extend(kept or [])
    return sittings, answered


def merge(
    weeks: list[tuple[date, date]], sittings: list[PlenarySitting]
) -> list[SittingWeek]:
    """Calendar weeks with the agenda's days in them; agenda days outside
    every calendar week (a special sitting) form a week of their own, one per
    calendar week they fall in."""
    merged = [SittingWeek(start=start, end=end) for start, end in weeks]
    for sitting in sittings:
        week = next(
            (
                w
                for w in merged
                if w.start <= sitting.date <= w.end
                or iso_week(w.start) == iso_week(sitting.date)
            ),
            None,
        )
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
    fetch: Fetch = fetch_page,
    now: Optional[datetime] = None,
    stored: Optional[SittingCalendar] = None,
    since: date = FEED_START,
) -> SittingCalendar:
    """Every sitting week from ``since`` to ``UPCOMING_WEEKS`` weeks ahead of
    ``today``, with each week's days where known.

    ``stored`` is the copy from the last run: its weeks stay even once the
    Sitzungskalender index stops linking their year, and its settled days are
    reused. Raises CalendarError when no source answers, so the caller keeps
    that copy rather than replacing it with nothing.
    """
    sources: list[str] = []
    weeks: list[tuple[date, date]] = []
    try:
        weeks = sitting_weeks(fetch, today, since)
        sources.append(CALENDAR_INDEX_URL)
    except Exception as exc:  # noqa: BLE001 — the agenda may still answer
        logger.warning("Sitzungskalender unavailable: %s", exc)
    # A stored week stays unless a fresh one covers the same calendar week.
    fresh = {iso_week(start) for start, _ in weeks}
    weeks += [
        (w.start, w.end)
        for w in (stored.weeks if stored else [])
        if iso_week(w.start) not in fresh
    ]
    weeks = sorted(
        {iso_week(start): (start, end) for start, end in weeks if end >= since}.values()
    )

    sittings, answered = week_sittings(fetch, weeks, today, stored)
    try:
        sittings += plenary_sittings(fetch)
        answered = True
    except Exception as exc:  # noqa: BLE001 — the calendar may still answer
        logger.warning("Bundestag agenda unavailable: %s", exc)
    if answered:
        sources.append(AGENDA_URL)
    if not sources:
        raise CalendarError("neither the Sitzungskalender nor the agenda answered")

    merged = [w for w in merge(weeks, sittings) if w.end >= since]
    past = [w for w in merged if w.end < today]
    ahead = [w for w in merged if w.end >= today][:UPCOMING_WEEKS]
    return SittingCalendar(
        parliament="bundestag",
        since=since,
        weeks=past + ahead,
        sources=sources,
        checked_at=now or datetime.now(timezone.utc),
    )
