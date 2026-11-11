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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as ElementTree
from pydantic import BaseModel, ConfigDict, ValidationError

from ingestion.connectors.bundestag_speeches.client import fetch_text
from ingestion.connectors.bundestag_speeches.constants import MDB_STAMMDATEN_FILE
from ingestion.connectors.bundestag_speeches.mdb import download_mdb_stammdaten
from ingestion.connectors.bundestag_speeches.utils import normalize_name_for_lookup
from ingestion.feed.calendar import parse_german_date
from ingestion.feed.models import FeedItem

logger = logging.getLogger(__name__)

Fetch = Callable[[str], str]

POLITICIAN_COLLECTION = "politicians"
SITE = "https://www.bundestag.de"
INDEX_URL = f"{SITE}/xml/v2/mdb/index.xml"
PROFILE_URL = f"{SITE}/xml/v2/mdb/biografien/{{bio_id}}.xml"
# A member's latest roll-call votes, as the profile page lists them (ten).
VOTES_URL = f"{SITE}/apps/na/abstimmunglinksByMdb.form?vaid={{bio_id}}"
# Every roll-call vote, newest first: its first date says whether there is a
# vote no stored list has yet.
ROLL_CALL_LIST_URL = (
    f"{SITE}/ajax/filterlist/de/parlament/plenum/abstimmung/liste/462112-462112"
)
# When that list cannot be read, the votes are fetched again after this long.
VOTES_FALLBACK_AGE = timedelta(days=7)
_BERLIN = ZoneInfo("Europe/Berlin")
STAMMDATEN_PATH = Path(__file__).resolve().parents[3] / MDB_STAMMDATEN_FILE
# The Stammdaten are republished every few weeks; a local copy older than
# this is fetched again, so members who joined since are found.
STAMMDATEN_MAX_AGE = timedelta(days=7)
# A member with no profile on bundestag.de (who left the Bundestag) is looked
# for again after this long, not on every run.
UNMATCHED_RETRY = timedelta(days=30)
# Between two requests to bundestag.de.
_PAUSE_S = 1.0
# Committees of the Bundestag carry ids a01..a99; every other Gremium (the
# Ältestenrat, subcommittees, Parlamentariergruppen, assemblies) does not.
_COMMITTEE_ID_PREFIX = "a"
OfficeKind = Literal["government", "parliament", "fraktion"]
# The Stammdaten offices shown under a name, by institution type, in this
# order. Under "Deutscher Bundestag" only the presidency counts: the rest are
# Gremien the profile lists anyway.
_OFFICE_KINDS: dict[str, OfficeKind] = {
    "Ministerium": "government",
    "Deutscher Bundestag": "parliament",
    "Fraktion/Gruppe": "fraktion",
}

MembershipLevel = Literal["chair", "vice_chair", "spokesperson", "member", "deputy"]
# Profile XML group tag -> how senior the role is. The role's own wording is
# the group's ``title`` attribute and is stored as is.
_LEVELS: dict[str, MembershipLevel] = {
    "mdbVorsitzGremien": "chair",
    "mdbVorsitzSonstigeGremien": "chair",
    "mdbStellvertretenderVorsitzGremien": "vice_chair",
    "mdbStellvVorsitzSonstigeGremien": "vice_chair",
    "mdbObleuteGremien": "spokesperson",
    "mdbSprecherGremien": "spokesperson",
    "mdbOrdentlichesMitgliedGremien": "member",
    "mdbOrdentlichesMitgliedSonstigeGremien": "member",
    "mdbStellvertretendesMitgliedGremien": "deputy",
    "mdbStellvertretendesMitgliedSonstigeGremien": "deputy",
}


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wp: int
    start: date
    end: Optional[date] = None


class Office(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "Bundesministerin", "Parlamentarischer Geschäftsführer", ...
    function: str
    # "Bundesministerium für ...", "Fraktion der ..."
    institution: str
    kind: OfficeKind


class Wahlkreis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str
    name: str


class Membership(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gremium: str
    # As published: "Obfrau", "Stellvertretendes Mitglied", ...
    role: str
    level: MembershipLevel
    kind: Literal["ausschuss", "sonstige"]
    url: Optional[str] = None


class DisclosureLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    # 1 for a line of a nested list: the clients and income under an activity.
    level: int = 0


class DisclosureEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The organisation first, then its functions, as the list on the profile.
    lines: list[DisclosureLine]


class DisclosureSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: Optional[str] = None
    entries: list[DisclosureEntry]


class Disclosures(BaseModel):
    """The Veröffentlichungspflichtige Angaben, structured as published: one
    section per heading, one entry per listed organisation."""

    model_config = ConfigDict(extra="forbid")

    sections: list[DisclosureSection]
    # A text standing on its own, e.g. "Keine veröffentlichungspflichtigen
    # Angaben."
    note: Optional[str] = None
    # The member's own explanation, linked from the profile.
    link: Optional[str] = None
    link_phrase: Optional[str] = None


VoteChoice = Literal["yes", "no", "abstain", "absent", "other"]
# The vote's CSS modifier on bundestag.de -> what it means.
_VOTE_CHOICES: dict[str, VoteChoice] = {
    "yes": "yes",
    "no": "no",
    "abstain": "abstain",
    "absent": "absent",
}


class RollCallVote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date
    title: str
    # The vote's own page on bundestag.de, with every member's vote.
    url: Optional[str] = None
    vote: VoteChoice
    # As published: "ja", "nein", "enthalten", "nicht abg."
    label: str


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


# --- MdB-Stammdaten ---------------------------------------------------------


@dataclass
class StammProfile:
    mdb_id: str
    title: Optional[str]
    first_name: str
    last_name: str
    name: str
    birth_date: Optional[date]
    partei: Optional[str]
    beruf: Optional[str]
    terms: list[Term]
    offices: list[Office]


def _text(node: Any, path: str) -> Optional[str]:
    value = node.findtext(path) if node is not None else None
    value = " ".join(value.split()) if value else ""
    return value or None


def _german_date(value: Optional[str]) -> Optional[date]:
    try:
        return datetime.strptime(value, "%d.%m.%Y").date() if value else None
    except ValueError:
        return None


def _current_name(mdb: Any) -> Any:
    """The name entry still in use: the one whose history has no end."""
    names = mdb.findall("NAMEN/NAME")
    return next((n for n in names if not _text(n, "HISTORIE_BIS")), names[-1])


def _offices(term: Any) -> list[Office]:
    """The offices held now in this Wahlperiode."""
    found: list[Office] = []
    for institution in term.findall("INSTITUTIONEN/INSTITUTION"):
        kind = _OFFICE_KINDS.get(_text(institution, "INSART_LANG") or "")
        function = _text(institution, "FKT_LANG")
        name = _text(institution, "INS_LANG")
        if (
            kind is None
            or not function
            or not name
            or _text(institution, "FKTINS_BIS")
            or _text(institution, "MDBINS_BIS")
        ):
            continue
        if kind == "parliament" and "präsident" not in function.lower():
            continue
        found.append(Office(function=function, institution=name, kind=kind))
    order = list(_OFFICE_KINDS.values())
    return sorted(found, key=lambda o: order.index(o.kind))


def parse_stammdaten_member(mdb: Any) -> StammProfile:
    name = _current_name(mdb)
    first = _text(name, "VORNAME") or ""
    last = _text(name, "NACHNAME") or ""
    terms: list[Term] = []
    latest: Any = None
    for term in mdb.findall("WAHLPERIODEN/WAHLPERIODE"):
        wp = _text(term, "WP")
        start = _german_date(_text(term, "MDBWP_VON"))
        if not wp or not wp.isdigit() or start is None:
            continue
        terms.append(
            Term(wp=int(wp), start=start, end=_german_date(_text(term, "MDBWP_BIS")))
        )
        if latest is None or int(wp) >= int(_text(latest, "WP") or 0):
            latest = term
    bio = mdb.find("BIOGRAFISCHE_ANGABEN")
    return StammProfile(
        mdb_id=_text(mdb, "ID") or "",
        title=_text(name, "AKAD_TITEL"),
        first_name=first,
        last_name=last,
        name=" ".join(
            p for p in (first, _text(name, "ADEL"), _text(name, "PRAEFIX"), last) if p
        ),
        birth_date=_german_date(_text(bio, "GEBURTSDATUM")),
        partei=_text(bio, "PARTEI_KURZ"),
        beruf=_text(bio, "BERUF"),
        terms=sorted(terms, key=lambda t: t.wp),
        offices=_offices(latest) if latest is not None else [],
    )


def read_stammdaten(path: Path, ids: Iterable[str]) -> dict[str, StammProfile]:
    wanted = set(ids)
    root = ElementTree.parse(str(path)).getroot()
    found: dict[str, StammProfile] = {}
    for mdb in root.findall("MDB"):
        mdb_id = _text(mdb, "ID")
        if mdb_id and mdb_id in wanted:
            found[mdb_id] = parse_stammdaten_member(mdb)
    return found


def load_stammdaten(
    ids: Iterable[str], path: Path = STAMMDATEN_PATH
) -> dict[str, StammProfile]:
    """The Stammdaten of these members, fetching a fresh copy first when the
    local one is missing or old."""
    if not path.exists() or (
        datetime.now(timezone.utc)
        - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        > STAMMDATEN_MAX_AGE
    ):
        download_mdb_stammdaten(path)
    return read_stammdaten(path, ids)


# --- bundestag.de profiles --------------------------------------------------


@dataclass(frozen=True)
class IndexEntry:
    bio_id: str
    # "Vorname Nachname", as the index's "Nachname, Vorname" reads.
    name: str
    last_changed: Optional[str]


def parse_index(xml_text: str) -> dict[str, IndexEntry]:
    root = ElementTree.fromstring(xml_text.encode("utf-8"))
    entries: dict[str, IndexEntry] = {}
    for mdb in root.iter("mdb"):
        bio_id = _text(mdb, "mdbID")
        raw = _text(mdb, "mdbName") or ""
        last, _, first = raw.partition(",")
        if bio_id:
            entries[bio_id] = IndexEntry(
                bio_id=bio_id,
                name=" ".join(f"{first} {last}".split()),
                last_changed=_text(mdb, "changedDateTime") or _text(mdb, "lastChanged"),
            )
    return entries


def candidates(profile: StammProfile, index: dict[str, IndexEntry]) -> list[str]:
    """The profiles that may be this member's, most likely first: the same
    full name, then the same surname. The birth date decides."""
    full = normalize_name_for_lookup(f"{profile.first_name} {profile.last_name}")
    last = normalize_name_for_lookup(profile.last_name)
    same_name: list[str] = []
    same_surname: list[str] = []
    for entry in index.values():
        name = normalize_name_for_lookup(entry.name)
        if name == full:
            same_name.append(entry.bio_id)
        elif last and name.endswith(f" {last}"):
            same_surname.append(entry.bio_id)
    return same_name + same_surname


class _DisclosureParser(HTMLParser):
    """The Angaben's HTML as sections of entries of lines. An ``<h3>`` opens
    a section, a top-level ``<ul>`` an entry, each ``<li>`` a line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[DisclosureSection] = []
        self.notes: list[str] = []
        self._depth = 0
        self._buffer: list[str] = []
        self._in: Optional[str] = None

    def _flush(self) -> None:
        text = " ".join("".join(self._buffer).split())
        self._buffer = []
        if not text:
            return
        if self._in == "h3":
            self.sections.append(DisclosureSection(heading=text, entries=[]))
        elif self._depth > 0:
            self._section().entries[-1].lines.append(
                DisclosureLine(text=text, level=self._depth - 1)
            )
        elif self.sections:
            self._section().entries.append(
                DisclosureEntry(lines=[DisclosureLine(text=text)])
            )
        else:
            self.notes.append(text)

    def _section(self) -> DisclosureSection:
        if not self.sections:
            self.sections.append(DisclosureSection(entries=[]))
        return self.sections[-1]

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("h3", "p", "li", "ul"):
            self._flush()
        if tag == "h3":
            self._in = "h3"
        elif tag == "ul":
            if self._depth == 0:
                self._section().entries.append(DisclosureEntry(lines=[]))
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h3", "p", "li", "ul"):
            self._flush()
        if tag == "h3":
            self._in = None
        elif tag == "ul":
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        self._buffer.append(data)


def parse_disclosures(
    html: Optional[str], link: Optional[str] = None, phrase: Optional[str] = None
) -> Optional[Disclosures]:
    if not html or not html.strip():
        return None
    parser = _DisclosureParser()
    parser.feed(html)
    parser.close()
    sections = [
        DisclosureSection(heading=s.heading, entries=[e for e in s.entries if e.lines])
        for s in parser.sections
    ]
    sections = [s for s in sections if s.entries or s.heading]
    note = " ".join(parser.notes) or None
    if not sections and note is None:
        return None
    return Disclosures(sections=sections, note=note, link=link, link_phrase=phrase)


class _RollCallParser(HTMLParser):
    """The rows of a member's vote table: date, linked title, vote."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.votes: list[RollCallVote] = []
        self._cells: Optional[list[str]] = None
        self._href: Optional[str] = None
        self._choice: VoteChoice = "other"

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self._cells, self._href, self._choice = None, None, "other"
        elif tag == "td":
            if self._cells is None:
                self._cells = []
            self._cells.append("")
        elif tag == "a" and self._cells is not None:
            self._href = attributes.get("href")
        elif tag == "span" and "a-vote" in (attributes.get("class") or ""):
            modifier = (attributes.get("class") or "").rpartition("--")[2]
            self._choice = _VOTE_CHOICES.get(modifier.strip(), "other")

    def handle_data(self, data: str) -> None:
        if self._cells:
            self._cells[-1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag != "tr" or not self._cells:
            return
        cells = [" ".join(c.split()) for c in self._cells]
        self._cells = None
        day = _german_date(cells[0]) if cells else None
        if day is None or len(cells) < 3 or not cells[1]:
            return
        self.votes.append(
            RollCallVote(
                day=day,
                title=cells[1],
                url=urljoin(SITE, self._href) if self._href else None,
                vote=self._choice,
                label=cells[2],
            )
        )


def parse_roll_calls(html: str) -> list[RollCallVote]:
    parser = _RollCallParser()
    parser.feed(html)
    parser.close()
    return parser.votes


def newest_roll_call(fetch: Fetch) -> Optional[date]:
    """The day of the latest roll-call vote; None when the list cannot be
    read, which makes the votes fall back to an age check."""
    try:
        return parse_german_date(fetch(ROLL_CALL_LIST_URL))
    except Exception as exc:  # noqa: BLE001 — the fallback still refreshes
        logger.warning("Roll-call list not read: %s", exc)
        return None


@dataclass
class BioProfile:
    bio_id: str
    birth_date: Optional[date]
    fraktion: Optional[str]
    partei: Optional[str]
    beruf: Optional[str]
    land: Optional[str]
    wahlkreis: Optional[Wahlkreis]
    elected: Optional[str]
    memberships: list[Membership]
    disclosures: Optional[Disclosures]
    photo_url: Optional[str]
    photo_credit: Optional[str]
    bio_url: Optional[str]
    source_stand: Optional[str]


def _memberships(info: Any) -> list[Membership]:
    found: list[Membership] = []
    groups = info.find("mdbMitgliedschaften") if info is not None else None
    for group in groups if groups is not None else []:
        level = _LEVELS.get(group.tag)
        role = " ".join((group.get("title") or "").split())
        if level is None or not role:
            continue
        for gremium in group:
            name = _text(gremium, "gremiumName")
            if not name:
                continue
            gremium_id = gremium.get("id") or ""
            committee = (
                gremium_id.startswith(_COMMITTEE_ID_PREFIX) and gremium_id[1:].isdigit()
            )
            found.append(
                Membership(
                    gremium=name,
                    role=role,
                    level=level,
                    kind="ausschuss" if committee else "sonstige",
                    url=_text(gremium, "gremiumURL"),
                )
            )
    return found


def parse_profile(xml_text: str) -> BioProfile:
    root = ElementTree.fromstring(xml_text.encode("utf-8"))
    info = root.find("mdbInfo")
    if info is None:
        raise ValueError("no mdbInfo in profile")
    number = _text(info, "mdbWahlkreis/mdbWahlkreisNummer")
    wk_name = _text(info, "mdbWahlkreis/mdbWahlkreisName")
    return BioProfile(
        bio_id=_text(info, "mdbID") or "",
        birth_date=_german_date(_text(info, "mdbGeburtsdatum")),
        fraktion=_text(info, "mdbFraktion"),
        partei=_text(info, "mdbPartei"),
        beruf=_text(info, "mdbBeruf"),
        land=_text(info, "mdbLand"),
        wahlkreis=Wahlkreis(number=number, name=wk_name)
        if number and wk_name
        else None,
        elected=_text(info, "mdbGewaehlt"),
        memberships=_memberships(info),
        disclosures=parse_disclosures(
            info.findtext("mdbVeroeffentlichungspflichtigeAngaben"),
            _text(info, "mdbVeroeffentlichungspflichtigeAngabenLink"),
            _text(info, "mdbVeroeffentlichungspflichtigeAngabenLinkPhrase"),
        ),
        photo_url=_text(root, "mdbMedien/mdbFoto/mdbFotoGrossURL"),
        photo_credit=_text(root, "mdbMedien/mdbFoto/mdbFotoCopyright"),
        bio_url=_text(info, "mdbBioURL"),
        source_stand=_text(root, "dokumentInfo/dokumentStand"),
    )


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


def read_politicians(db: Any, ids: Iterable[str]) -> dict[str, Politician]:
    refs = [db.collection(POLITICIAN_COLLECTION).document(i) for i in ids]
    found: dict[str, Politician] = {}
    for snapshot in db.get_all(refs) if refs else []:
        if not snapshot.exists:
            continue
        try:
            found[snapshot.id] = Politician.model_validate(snapshot.to_dict())
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
    if stored.bio_id is None:
        return now - stored.fetched_at >= UNMATCHED_RETRY
    entry = index.get(stored.bio_id)
    # Gone from the index: the member left; the stored record stays as it is.
    return entry is not None and entry.last_changed != stored.last_changed


def votes_are_due(
    stored: Optional[Politician], newest: Optional[date], now: datetime
) -> bool:
    """Whether a stored member's votes may be missing one: they were read on
    or before the day of the latest vote."""
    if stored is None or stored.bio_id is None:
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


def refresh_politicians(
    db: Any,
    ids: list[str],
    *,
    fetch: Fetch = fetch_text,
    stammdaten: Callable[[list[str]], dict[str, StammProfile]] = load_stammdaten,
    now: Optional[datetime] = None,
    out_of_time: Callable[[], bool] = lambda: False,
    pause: Callable[[], None] = lambda: time.sleep(_PAUSE_S),
) -> RefreshReport:
    """Store the record of each of these speakers that is missing or whose
    profile changed since, and the votes of each whose list may be missing
    a newer vote. ``db=None`` is a dry run: the records are printed.

    One member failing is logged and skipped; the next run tries again.
    """
    now = now or datetime.now(timezone.utc)
    report = RefreshReport()
    if not ids:
        return report
    stored = read_politicians(db, ids) if db is not None else {}
    index = parse_index(fetch(INDEX_URL))
    due = [i for i in ids if is_due(stored.get(i), index, now)]
    newest = newest_roll_call(fetch)
    votes_due = [
        i for i in ids if i not in due and votes_are_due(stored.get(i), newest, now)
    ]
    profiles = stammdaten(due) if due else {}
    for mdb_id in [*due, *votes_due]:
        if out_of_time():
            report.out_of_time = True
            break
        record = stored.get(mdb_id)
        try:
            if record is not None and mdb_id in votes_due:
                politician = with_votes(record, fetch, pause, now)
            elif (stamm := profiles.get(mdb_id)) is None:
                report.not_members.append(mdb_id)
                continue
            else:
                bio = _find_profile(stamm, record, index, fetch, pause)
                politician = merge(
                    stamm, bio, index.get(bio.bio_id) if bio else None, now
                )
                if bio is not None:
                    politician = with_votes(politician, fetch, pause, now)
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
