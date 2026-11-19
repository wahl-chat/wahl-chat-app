# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""What the Bundestag publishes about its members, read as published.

- The MdB-Stammdaten, keyed by the same ID the Plenarprotokoll gives each
  ``<redner>``: every Wahlperiode with its dates, and the offices held.
- The XML behind the profile pages on bundestag.de (``xml/v2/mdb``): the
  index of all members with when each profile last changed, and each
  profile's Gremien with their roles, Wahlkreis, photo and the
  Veröffentlichungspflichtige Angaben.
- The member's latest namentliche Abstimmungen as the profile page lists
  them, and the list of all roll-call votes, newest first.

Parsing only; ``politicians`` decides what to fetch and stores the record.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urljoin

import defusedxml.ElementTree as ElementTree
from pydantic import BaseModel, ConfigDict

from ingestion.connectors.bundestag_speeches.mdb import (
    DEFAULT_MDB_PATH,
    ensure_mdb_file,
)
from ingestion.connectors.bundestag_speeches.utils import (
    normalize_name_for_lookup,
    normalize_whitespace,
    parse_dotted_date,
)
from ingestion.feed.calendar import parse_german_date

logger = logging.getLogger(__name__)

Fetch = Callable[[str], str]

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
# The Stammdaten are republished every few weeks; a local copy older than
# this is fetched again, so members who joined since are found.
STAMMDATEN_MAX_AGE = timedelta(days=7)
# A slow download must not eat the feed job's time cap: one retry, not four.
_STAMMDATEN_ATTEMPTS = 2
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
    if node is None:
        return None
    return normalize_whitespace(node.findtext(path)) or None


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
        start = parse_dotted_date(_text(term, "MDBWP_VON"))
        if not wp or not wp.isdigit() or start is None:
            continue
        terms.append(
            Term(
                wp=int(wp), start=start, end=parse_dotted_date(_text(term, "MDBWP_BIS"))
            )
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
        birth_date=parse_dotted_date(_text(bio, "GEBURTSDATUM")),
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
    ids: Iterable[str], path: Path = DEFAULT_MDB_PATH
) -> dict[str, StammProfile]:
    """The Stammdaten of these members, fetching a fresh copy first when the
    local one is missing or old."""
    ensure_mdb_file(path, max_age=STAMMDATEN_MAX_AGE, attempts=_STAMMDATEN_ATTEMPTS)
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
        day = parse_dotted_date(cells[0]) if cells else None
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
        birth_date=parse_dotted_date(_text(info, "mdbGeburtsdatum")),
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
