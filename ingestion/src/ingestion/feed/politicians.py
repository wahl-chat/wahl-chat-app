# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Who spoke: one record per member of the Bundestag, as the Bundestag
publishes it, in Firestore ``politicians/{mdb_id}``.

Two official sources, joined on name and birth date:

- the MdB-Stammdaten (``MDB_STAMMDATEN_URL``), keyed by the same ID the
  Plenarprotokoll gives each ``<redner>``: every Wahlperiode with its dates,
  and the offices held (minister, Fraktion functions, the presidency);
- the XML behind the profile pages on bundestag.de (``xml/v2/mdb``): the
  current Gremien with their roles, Wahlkreis, photo and the
  Veröffentlichungspflichtige Angaben. It has its own IDs and none of the
  Stammdaten's, so a member's profile is found once by name, confirmed by
  birth date, and its ID kept. The same ID gives the member's latest
  namentliche Abstimmungen, the list the profile page shows.

Nothing is summarised or reworded: texts are stored as published, whitespace
aside. The index of all members says when each profile last changed, so a
profile is fetched again only after it did; the votes are fetched again once
the Bundestag's list of roll-call votes has a newer one.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, ValidationError

from ingestion.feed.calendar import fetch_page
from ingestion.feed.models import FeedItem
from ingestion.feed.speaker_parties import (
    OutsideSpeaker,
    Roster,
    load_roster,
)
from ingestion.feed.politician_sources import (
    INDEX_URL,
    PROFILE_URL,
    VOTES_URL,
    BioProfile,
    Disclosures,
    Fetch,
    IndexEntry,
    Membership,
    Office,
    RollCallVote,
    StammProfile,
    Term,
    Wahlkreis,
    candidates,
    load_stammdaten,
    newest_roll_call,
    parse_index,
    parse_profile,
    parse_roll_calls,
)

logger = logging.getLogger(__name__)

POLITICIAN_COLLECTION = "politicians"
# When the list of roll-call votes cannot be read, a member's votes are
# fetched again after this long.
VOTES_FALLBACK_AGE = timedelta(days=7)
_BERLIN = ZoneInfo("Europe/Berlin")
# A record is read again after this long even when its profile did not
# change: the offices come from the Stammdaten, which the profile's change
# date does not track. A member with no profile is looked for again as often.
RECHECK_AFTER = timedelta(days=30)
# Between two requests to bundestag.de.
_PAUSE_S = 1.0


class Politician(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The Stammdaten ID, as the protocol's <redner id>.
    mdb_id: str
    # The ID of the member's profile on bundestag.de; None for a member who
    # has none (no longer in the Bundestag).
    bio_id: Optional[str] = None
    title: Optional[str] = None
    first_name: str
    last_name: str
    # Full name without the academic title: "Sanae Abdi", "Johann David Wadephul".
    name: str
    birth_date: Optional[date] = None
    fraktion: Optional[str] = None
    partei: Optional[str] = None
    beruf: Optional[str] = None
    land: Optional[str] = None
    wahlkreis: Optional[Wahlkreis] = None
    # As published: "direkt" or "Landesliste".
    elected: Optional[str] = None
    offices: list[Office] = []
    terms: list[Term] = []
    memberships: list[Membership] = []
    disclosures: Optional[Disclosures] = None
    photo_url: Optional[str] = None
    photo_credit: Optional[str] = None
    bio_url: Optional[str] = None
    # The profile's own dates: "Stand" as printed, and when it last changed
    # according to the index (which decides whether to fetch it again).
    source_stand: Optional[str] = None
    last_changed: Optional[str] = None
    fetched_at: datetime
    # The latest namentliche Abstimmungen, newest first, and when they were
    # read; none for a member without a profile.
    votes: list[RollCallVote] = []
    votes_checked_at: Optional[datetime] = None
    # "roster" for a speaker from outside the Bundestag, whose record holds
    # only the party and office from ``government_speakers.json``.
    source: Literal["bundestag", "roster"] = "bundestag"


def merge(
    stamm: StammProfile,
    bio: Optional[BioProfile],
    entry: Optional[IndexEntry],
    now: datetime,
) -> Politician:
    return Politician(
        mdb_id=stamm.mdb_id,
        bio_id=bio.bio_id if bio else None,
        title=stamm.title,
        first_name=stamm.first_name,
        last_name=stamm.last_name,
        name=stamm.name,
        birth_date=stamm.birth_date,
        fraktion=bio.fraktion if bio else None,
        partei=(bio.partei if bio else None) or stamm.partei,
        beruf=(bio.beruf if bio else None) or stamm.beruf,
        land=bio.land if bio else None,
        wahlkreis=bio.wahlkreis if bio else None,
        elected=bio.elected if bio else None,
        offices=stamm.offices,
        terms=stamm.terms,
        memberships=bio.memberships if bio else [],
        disclosures=bio.disclosures if bio else None,
        photo_url=bio.photo_url if bio else None,
        photo_credit=bio.photo_credit if bio else None,
        bio_url=bio.bio_url if bio else None,
        source_stand=bio.source_stand if bio else None,
        last_changed=entry.last_changed if entry else None,
        fetched_at=now,
    )


def outside_record(outside: OutsideSpeaker, mdb_id: str, now: datetime) -> Politician:
    first, _, last = outside.name.rpartition(" ")
    return Politician(
        mdb_id=mdb_id,
        first_name=first,
        last_name=last,
        name=outside.name,
        partei=outside.party,
        offices=[
            Office(
                function=outside.office,
                institution=outside.institution,
                kind="government",
            )
        ],
        fetched_at=now,
        source="roster",
    )


# --- the refresh ------------------------------------------------------------


def speaker_ids(items: Iterable[FeedItem]) -> list[str]:
    """Every identified speaker of these debates, once."""
    found: dict[str, None] = {}
    for item in items:
        for party in item.debate.parties if item.debate else []:
            for speaker in party.speakers:
                if speaker.mdb_id:
                    found.setdefault(speaker.mdb_id)
    return list(found)


def speakers_without_id(items: Iterable[FeedItem]) -> int:
    """Speaker chips the protocol never identified. Speaker facts reach only
    the days a run covers, so a count that stays high after a run points at
    stored days no run has reached since the facts were added."""
    return sum(
        1
        for item in items
        for party in (item.debate.parties if item.debate else [])
        for speaker in party.speakers
        if not speaker.mdb_id
    )


def speaker_names(items: Iterable[FeedItem]) -> dict[str, str]:
    """MdB ID -> the name the debate shows, for speakers from outside the
    Bundestag whom the roster knows by name only."""
    return {
        speaker.mdb_id: speaker.name
        for item in items
        for party in (item.debate.parties if item.debate else [])
        for speaker in party.speakers
        if speaker.mdb_id
    }


def read_politicians(db: Any, ids: Iterable[str]) -> dict[str, Politician]:
    refs = [db.collection(POLITICIAN_COLLECTION).document(i) for i in ids]
    found: dict[str, Politician] = {}
    for snapshot in db.get_all(refs) if refs else []:
        if not snapshot.exists:
            continue
        # A field the model no longer has must not make every record due at
        # once; it goes with the next write.
        data = {
            key: value
            for key, value in (snapshot.to_dict() or {}).items()
            if key in Politician.model_fields
        }
        try:
            found[snapshot.id] = Politician.model_validate(data)
        except ValidationError:
            logger.info("Stored politician %s has an older shape", snapshot.id)
    return found


def write_politician(db: Any, politician: Politician) -> None:
    db.collection(POLITICIAN_COLLECTION).document(politician.mdb_id).set(
        politician.model_dump(mode="json")
    )


def is_due(
    stored: Optional[Politician], index: dict[str, IndexEntry], now: datetime
) -> bool:
    if stored is None:
        return True
    age = now - stored.fetched_at
    if stored.bio_id is None:
        return age >= RECHECK_AFTER
    entry = index.get(stored.bio_id)
    # Gone from the index: the member left; the stored record stays as it is.
    if entry is None:
        return False
    return entry.last_changed != stored.last_changed or age >= RECHECK_AFTER


def votes_are_due(
    stored: Optional[Politician],
    index: dict[str, IndexEntry],
    newest: Optional[date],
    now: datetime,
) -> bool:
    """Whether a stored member's votes may be missing one: they were read on
    or before the day of the latest vote. A member who left keeps the votes
    last read; their page lists none any more."""
    if stored is None or stored.bio_id not in index:
        return False
    checked = stored.votes_checked_at
    if checked is None:
        return True
    if newest is None:
        return now - checked >= VOTES_FALLBACK_AGE
    return checked.astimezone(_BERLIN).date() <= newest


def with_votes(
    politician: Politician, fetch: Fetch, pause: Callable[[], None], now: datetime
) -> Politician:
    pause()
    votes = parse_roll_calls(fetch(VOTES_URL.format(bio_id=politician.bio_id)))
    if not votes and politician.votes:
        # An empty table where votes were listed is a page that changed, not
        # a member who never voted: keep what was read.
        logger.warning(
            "No votes read for politician %s; keeping the stored ones",
            politician.mdb_id,
        )
        votes = politician.votes
    return politician.model_copy(update={"votes": votes, "votes_checked_at": now})


@dataclass
class RefreshReport:
    written: list[str] = field(default_factory=list)
    # Speakers the Stammdaten do not know: Bundesrat members, ministers from
    # outside the Bundestag, guests.
    not_members: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    out_of_time: bool = False


def _find_profile(
    stamm: StammProfile,
    stored: Optional[Politician],
    index: dict[str, IndexEntry],
    fetch: Fetch,
    pause: Callable[[], None],
) -> Optional[BioProfile]:
    if stored is not None and stored.bio_id in index:
        pause()
        return parse_profile(fetch(PROFILE_URL.format(bio_id=stored.bio_id)))
    unread: Optional[Exception] = None
    for bio_id in candidates(stamm, index):
        pause()
        try:
            profile = parse_profile(fetch(PROFILE_URL.format(bio_id=bio_id)))
        except Exception as exc:  # noqa: BLE001 — a namesake's page may fail
            unread = exc
            continue
        if stamm.birth_date is not None and profile.birth_date == stamm.birth_date:
            return profile
    # A page that could not be read may have been theirs: try again next run
    # rather than store them as having no profile.
    if unread is not None:
        raise unread
    return None


def _with_votes_if_read(
    politician: Politician,
    stored: Optional[Politician],
    fetch: Fetch,
    pause: Callable[[], None],
    now: datetime,
) -> Politician:
    """The fresh profile with its votes. Votes that cannot be read keep the
    profile: it is stored with the votes last read and unchecked, so the next
    run fetches only those."""
    if stored is not None and stored.bio_id == politician.bio_id:
        politician = politician.model_copy(update={"votes": stored.votes})
    try:
        return with_votes(politician, fetch, pause, now)
    except Exception as exc:  # noqa: BLE001 — the profile stands on its own
        logger.warning("Votes of politician %s not read: %s", politician.mdb_id, exc)
        return politician


def refresh_politicians(
    db: Any,
    ids: list[str],
    *,
    fetch: Fetch = fetch_page,
    stammdaten: Callable[[list[str]], dict[str, StammProfile]] = load_stammdaten,
    now: Optional[datetime] = None,
    out_of_time: Callable[[], bool] = lambda: False,
    pause: Callable[[], None] = lambda: time.sleep(_PAUSE_S),
    roster: Callable[[], Roster] = load_roster,
    names: Optional[dict[str, str]] = None,
) -> RefreshReport:
    """Store the record of each of these speakers that is missing or whose
    profile changed since, and the votes of each whose list may be missing
    a newer vote. ``db=None`` is a dry run: the records are printed.

    One member failing is logged and skipped; the next run tries again. The
    budget is checked before every request that may be slow, not only
    between members: the feed's job cap does not wait for bundestag.de.
    """
    now = now or datetime.now(timezone.utc)
    report = RefreshReport()
    if not ids:
        return report
    if out_of_time():
        report.out_of_time = True
        return report
    stored = read_politicians(db, ids) if db is not None else {}
    index = parse_index(fetch(INDEX_URL))
    due = [i for i in ids if is_due(stored.get(i), index, now)]
    newest = newest_roll_call(fetch)
    votes_due = [
        i
        for i in ids
        if i not in due and votes_are_due(stored.get(i), index, newest, now)
    ]
    profiles: dict[str, StammProfile] = {}
    if due and not out_of_time():
        try:
            profiles = stammdaten(due)
        except Exception as exc:  # noqa: BLE001 — the votes can still be read
            logger.warning("MdB-Stammdaten not read: %s", exc)
            report.failed.extend(due)
            due = []
    known: Optional[Roster] = None
    for mdb_id in [*due, *votes_due]:
        if out_of_time():
            report.out_of_time = True
            break
        record = stored.get(mdb_id)
        try:
            if record is not None and mdb_id in votes_due:
                politician = with_votes(record, fetch, pause, now)
            elif (stamm := profiles.get(mdb_id)) is None:
                known = known or roster()
                outside = known.find(mdb_id, (names or {}).get(mdb_id, ""))
                if outside is None:
                    report.not_members.append(mdb_id)
                    continue
                politician = outside_record(outside, mdb_id, now)
            else:
                bio = _find_profile(stamm, record, index, fetch, pause)
                politician = merge(
                    stamm, bio, index.get(bio.bio_id) if bio else None, now
                )
                if bio is not None:
                    politician = _with_votes_if_read(
                        politician, record, fetch, pause, now
                    )
        except Exception as exc:  # noqa: BLE001 — one member must not stop the rest
            logger.warning("Politician %s not refreshed: %s", mdb_id, exc)
            report.failed.append(mdb_id)
            continue
        if db is None:
            print(politician.model_dump_json(indent=2))
        else:
            write_politician(db, politician)
        report.written.append(mdb_id)
    return report
