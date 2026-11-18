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

The display texts (offices, Gremien and roles, Beruf, roll-call titles, the
headings of the Angaben) are translated in the run that writes the record,
each distinct text once, and stored next to the German as pairs. Names of
people, parties, Fraktionen, Wahlkreise and the disclosed organisations are
proper names and stay as published. A record whose translation is missing or
stale is translated in a later run without being fetched again.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ingestion.feed.builder import FeedBuilder
from ingestion.feed.calendar import fetch_page
from ingestion.feed.models import TRANSLATED_LOCALES, FeedItem, Locale, TranslatedText
from ingestion.feed.prompts import (
    POLITICIAN_TRANSLATION_PROMPT_VERSION,
    format_politician_translation_prompt,
)
from ingestion.feed.translate import request_segments, segment_line, text_problems
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
# Display texts per translation call: short, and shared by many records.
_TEXT_BATCH = 40


class PoliticianTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Each display text of the record (``display_texts``) and its translation.
    # A text missing here failed its check; the web shows it in German, and
    # the next run tries it again.
    texts: list[TranslatedText]
    # Hash of the German display texts it was made for.
    source_hash: str
    prompt_version: str
    generated_at: datetime


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
    # The display texts in every other locale (see ``display_texts``).
    translations: dict[Locale, PoliticianTranslation] = Field(default_factory=dict)


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


# --- translation ------------------------------------------------------------


def display_texts(politician: Politician) -> list[str]:
    """Every German text of the record the web shows that is not a proper
    name, once each, in a stable order."""
    texts: list[Optional[str]] = []
    for office in politician.offices:
        texts += [office.function, office.institution]
    for membership in politician.memberships:
        texts += [membership.gremium, membership.role]
    texts.append(politician.beruf)
    texts += [vote.title for vote in politician.votes]
    disclosures = politician.disclosures
    if disclosures is not None:
        texts += [section.heading for section in disclosures.sections]
        texts += [disclosures.note, disclosures.link_phrase]
    return list(dict.fromkeys(t for t in texts if t and t.strip()))


def texts_hash(politician: Politician) -> str:
    return hashlib.sha256(
        json.dumps(display_texts(politician), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def needs_politician_translation(politician: Politician, locale: Locale) -> bool:
    texts = display_texts(politician)
    current = politician.translations.get(locale)
    if not texts:
        return False
    if current is None:
        return True
    return (
        current.source_hash != texts_hash(politician)
        or current.prompt_version != POLITICIAN_TRANSLATION_PROMPT_VERSION
        or not set(texts) <= {t.source for t in current.texts}
    )


def known_translations(records: Iterable[Politician], locale: Locale) -> dict[str, str]:
    """German -> translation of every text stored records already hold under
    the current prompt: each was checked when it was made, and many members
    share a Gremium, a role or a vote."""
    known: dict[str, str] = {}
    for record in records:
        current = record.translations.get(locale)
        if current is not None and (
            current.prompt_version == POLITICIAN_TRANSLATION_PROMPT_VERSION
        ):
            known.update({t.source: t.text for t in current.texts})
    return known


def _translate_texts(
    texts: list[str],
    builder: FeedBuilder,
    out_of_time: Callable[[], bool],
) -> tuple[dict[str, str], bool]:
    """German -> translation of the texts that passed their checks, and
    whether every batch was asked: a batch the budget or a failed call
    skipped is tried again next run."""
    found: dict[str, str] = {}
    asked_all = True
    for start in range(0, len(texts), _TEXT_BATCH):
        if out_of_time():
            return found, False
        batch = texts[start : start + _TEXT_BATCH]
        lines = [segment_line(f"S{i + 1}", t) for i, t in enumerate(batch)]
        answers, _ = request_segments(
            builder,
            format_politician_translation_prompt("Bundestag", "\n".join(lines)),
            f"{len(batch)} politician texts",
        )
        if not answers:
            asked_all = False
            continue
        for i, german in enumerate(batch):
            text = " ".join(answers.get(f"S{i + 1}", "").split())
            problems = text_problems("text", german, text)
            if problems:
                logger.warning("Not storing translation of %r: %s", german, problems)
                continue
            found[german] = text
    return found, asked_all


def translate_politicians(
    records: list[Politician],
    builder: FeedBuilder,
    *,
    known: Optional[dict[Locale, dict[str, str]]] = None,
    now: datetime,
    out_of_time: Callable[[], bool] = lambda: False,
    locales: tuple[Locale, ...] = TRANSLATED_LOCALES,
) -> list[Politician]:
    """``records`` with their translations brought up to date, in their
    order. Only texts no record holds yet are sent, in batches. A record
    keeps its stored translation, stale or not, until a batch has been asked
    for every text it lacks: a stale pair still beats German."""
    out = list(records)
    for locale in locales:
        cache = dict((known or {}).get(locale, {}))
        cache.update(known_translations(out, locale))
        todo = [n for n, r in enumerate(out) if needs_politician_translation(r, locale)]
        missing = list(
            dict.fromkeys(
                t for n in todo for t in display_texts(out[n]) if t not in cache
            )
        )
        asked_all = True
        if missing:
            found, asked_all = _translate_texts(missing, builder, out_of_time)
            cache.update(found)
        for n in todo:
            record = out[n]
            texts = display_texts(record)
            if not asked_all and not set(texts) <= set(cache):
                continue
            pairs = [
                TranslatedText(source=t, text=cache[t]) for t in texts if t in cache
            ]
            translations = {k: v for k, v in record.translations.items() if k != locale}
            if pairs:
                translations[locale] = PoliticianTranslation(
                    texts=pairs,
                    source_hash=texts_hash(record),
                    prompt_version=POLITICIAN_TRANSLATION_PROMPT_VERSION,
                    generated_at=now,
                )
            out[n] = record.model_copy(update={"translations": translations})
    return out


def _carry_translations(fresh: Politician, stored: Optional[Politician]) -> Politician:
    """A record read again keeps the translations of its texts that are still
    there, until the translation pass renews them."""
    if stored is None or not stored.translations:
        return fresh
    texts = set(display_texts(fresh))
    return fresh.model_copy(
        update={
            "translations": {
                locale: t.model_copy(
                    update={"texts": [p for p in t.texts if p.source in texts]}
                )
                for locale, t in stored.translations.items()
            }
        }
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
    builder: Optional[FeedBuilder] = None,
) -> RefreshReport:
    """Store the record of each of these speakers that is missing or whose
    profile changed since, and the votes of each whose list may be missing
    a newer vote. ``db=None`` is a dry run: the records are printed.

    With a ``builder``, every record written is translated first, and so is
    every stored one among ``ids`` whose translation is missing or stale.

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
    fresh: list[Politician] = []
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
        fresh.append(_carry_translations(politician, record))
    to_write = _translated(fresh, stored, builder, now, out_of_time)
    for politician in to_write:
        if db is None:
            print(politician.model_dump_json(indent=2))
        else:
            write_politician(db, politician)
        report.written.append(politician.mdb_id)
    return report


def _translated(
    fresh: list[Politician],
    stored: dict[str, Politician],
    builder: Optional[FeedBuilder],
    now: datetime,
    out_of_time: Callable[[], bool],
) -> list[Politician]:
    """The fresh records, translated, then the stored ones whose translation
    this pass renewed. Without a builder, the fresh records as they are."""
    if builder is None:
        return fresh
    written = {p.mdb_id for p in fresh}
    stale = [
        record
        for mdb_id, record in stored.items()
        if mdb_id not in written
        and any(needs_politician_translation(record, loc) for loc in TRANSLATED_LOCALES)
    ]
    known = {
        locale: known_translations(stored.values(), locale)
        for locale in TRANSLATED_LOCALES
    }
    renewed = translate_politicians(
        [*fresh, *stale], builder, known=known, now=now, out_of_time=out_of_time
    )
    return renewed[: len(fresh)] + [
        new for old, new in zip(stale, renewed[len(fresh) :]) if new != old
    ]


def translate_stored_politicians(
    db: Any,
    ids: list[str],
    builder: FeedBuilder,
    *,
    now: Optional[datetime] = None,
    out_of_time: Callable[[], bool] = lambda: False,
) -> list[str]:
    """Translate the stored records of these speakers whose translation is
    missing or stale, without reading bundestag.de. Returns the ids written."""
    now = now or datetime.now(timezone.utc)
    stored = read_politicians(db, ids) if ids else {}
    written = _translated([], stored, builder, now, out_of_time)
    for politician in written:
        write_politician(db, politician)
    return [p.mdb_id for p in written]
