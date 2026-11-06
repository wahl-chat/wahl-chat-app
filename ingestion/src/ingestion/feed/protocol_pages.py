# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Speech order, page anchors and cross-source twins from the protocol XML.

The corpus knows neither the order of the speeches in a debate (a scroll
returns points by id, and op.tv speeches carry no time of day) nor, for
openparliament.tv records, the protocol page: their DIP twin was merged away at
ingest. The protocol XML next to the PDF lists every speech in the order it was
given, with its printed page, and under each agenda item its title. The PDF
opens with pages of contents before printed page one of the sitting, so a
printed page becomes a PDF page only through the PDF's own page labels.

Speeches are matched to it by speaker and agenda item. Where the two sources
file a debate under different items (a joint debate the protocol keeps under
"Tagesordnungspunkt 24" and openparliament.tv under "Zusatzpunkt 19"), the
speaker is looked up in the protocol block that holds most of the item's
speakers. Two corpus speeches matched to the same protocol speech are one
speech from both sources; the openparliament.tv one is kept, as everywhere.

Everything that reads "the first speech" depends on that order: the Fraktion
that opened the debate, the opening quote, the citations, the video. So a
debate whose protocol XML or PDF cannot be read is not built at all, rather
than built in an arbitrary order or without its pages; the next run tries
again. Its Drucksachen and interjections come from the XML alone.

The title only fills in for an item no corpus record titles (openparliament.tv
carries one; DIP speeches carry only the item number), so a debate that only
DIP holds is not shown as "Tagesordnungspunkt 7".
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Optional

import defusedxml.ElementTree as ElementTree
from pypdf import PdfReader

from ingestion.connectors.bundestag_speeches.client import fetch_bytes, fetch_text
from ingestion.connectors.bundestag_speeches.parser import parse_speeches_from_xml
from ingestion.feed.documents import drucksachen_in_text
from ingestion.feed.reader import AgendaItem, SittingDay, Speech, numbered_label
from ingestion.speech_key import agenda_slug_from_top_id, slugify_speaker

logger = logging.getLogger(__name__)

# Bundestag protocol PDFs live at dserver.bundestag.de/btp/{wp}/{wp}{nnn}.pdf
# with the XML beside them; nothing else is rewritten into an XML URL.
_PROTOCOL_PDF_RE = re.compile(r"^https://dserver\.bundestag\.de/btp/\d+/\d+\.pdf$")
_PROTOCOL_ID_RE = re.compile(r"^(\d+)/(\d+)$")
# de-{ep}-{session}-{speaker}-{agenda}; the agenda part may be empty.
_KEY_SPEAKER_RE = re.compile(r"^de-\d+-\d+-(.*)-(?:(?:top|zp)\d+)?$")
# A bill has no title line of its own; its name is inside the item's text
# ("Erste Beratung des … eingebrachten Entwurfs eines Dritten Gesetzes zur …"),
# in the genitive. An adjective before it ("Dritten") and the noun go back to
# the nominative: "Drittes Gesetz zur …", "Sportfördergesetz".
_BILL_RE = re.compile(
    r"Entwurfs eines (?:(?:…|\.\.\.)\s*)?(?:(\w+)en\s+)?(\w*[Gg]esetz)es\b(.*)$"
)
_TITLE_LINE = "T_fett"
# The lines of an item's call-up that list the documents it deals with. Speech
# paragraphs cite other Drucksachen too, so only these count.
_DOCUMENT_LINE = "T_Drs"
# One <kommentar> can record several reactions, separated by dashes:
# "(Beifall bei der SPD – Zuruf von der AfD: Unsinn! – Lachen bei der AfD)".
_REACTION_SEPARATOR = re.compile(r"\s+[–—-]\s+")
# The reactions that show conflict: calls from the floor, named or not,
# objections, mocking laughter, unrest. Applause and Heiterkeit (amusement)
# do not.
_CONFLICT_REACTION = re.compile(
    r"^(?:Weitere\s+)?(?:Zurufe?|Gegenrufe?|Widerspruch|Lachen|Unruhe|Pfui)\b"
    r"|^(?!Beifall)[^:\[\]]{2,80}\[[^\]]+\]:"
)
_ITEM_TEXT = ("T_NaS", "T_ZP_NaS")

FetchText = Callable[[str], str]
# A sentence is looked for by its first letters only: enough to be unique on
# a page, and a sentence cut at the snippet limit still matches.
_FIND_LETTERS = 60


def _letters(text: str) -> str:
    """Lowercase letters only. A PDF page breaks words at line ends
    ("Klima- schutz") and prints line numbers; the corpus text does neither."""
    return "".join(ch for ch in text.casefold() if ch.isalpha())


class ProtocolPdf:
    """The protocol PDF's pages: which PDF page carries a printed page, and
    on which page a sentence stands. Page text is read only when asked for."""

    def __init__(self, reader: PdfReader):
        self._reader = reader
        self._pages = {
            int(label): n
            for n, label in enumerate(reader.page_labels, 1)
            if label.isdigit()
        }
        self._texts: dict[int, str] = {}

    @classmethod
    def from_bytes(cls, pdf: bytes) -> ProtocolPdf:
        return cls(PdfReader(io.BytesIO(pdf)))

    def page(self, printed: int) -> Optional[int]:
        """The 1-based PDF page printed with ``printed``. The contents pages
        are labelled I, II, …; the sitting's pages by their printed number."""
        return self._pages.get(printed)

    def _text(self, page: int) -> str:
        if page not in self._texts:
            self._texts[page] = _letters(
                self._reader.pages[page - 1].extract_text() or ""
            )
        return self._texts[page]

    def page_of(self, sentence: str, first: int) -> Optional[int]:
        """The page the sentence stands on: the first from ``first`` on, else
        any before it.

        Not bounded by the next speech: in a Befragung the corpus holds all
        of a minister's answers as one speech, while the protocol interleaves
        them with the questions over dozens of pages, and the same members
        ask so often that a speech can be placed on another of their turns.
        """
        needle = _letters(sentence)[:_FIND_LETTERS]
        if not needle:
            return None
        count = len(self._reader.pages)
        order = [*range(first, count + 1), *range(1, min(first, count + 1))]
        return next((n for n in order if needle in self._text(n)), None)


ReadPdf = Callable[[str], ProtocolPdf]


@dataclass(frozen=True)
class ProtocolSpeech:
    position: int
    # The page number printed on the protocol; None when the table of
    # contents has no entry.
    printed_page: Optional[int]
    speaker: str
    agenda: str
    # Conflict reactions the protocol records during the speech.
    interjections: int = 0


@dataclass
class ProtocolIndex:
    speeches: list[ProtocolSpeech] = field(default_factory=list)
    session_date: Optional[date] = None
    # agenda slug -> the item's title as the protocol prints it
    titles: dict[str, str] = field(default_factory=dict)
    # agenda slug -> the Drucksachen its call-up lists
    documents: dict[str, list[str]] = field(default_factory=dict)


def read_protocol_pdf(pdf_url: str) -> ProtocolPdf:
    return ProtocolPdf.from_bytes(fetch_bytes(pdf_url))


def protocol_xml_url(pdf_url: str) -> Optional[str]:
    base = pdf_url.split("#", 1)[0]
    if not _PROTOCOL_PDF_RE.match(base):
        return None
    return base[: -len(".pdf")] + ".xml"


def _session_date(root: Any) -> Optional[date]:
    raw = root.get("sitzung-datum")
    try:
        return datetime.strptime(raw, "%d.%m.%Y").date() if raw else None
    except ValueError:
        return None


def _text(element: Any) -> str:
    return " ".join("".join(element.itertext()).split())


def _bill_title(text: str) -> Optional[str]:
    match = _BILL_RE.search(text)
    if match is None:
        return None
    adjective, noun, rest = match.groups()
    head = f"{adjective}es {noun}" if adjective else noun
    return f"{head}{rest}".strip()


def _item_title(top: Any) -> Optional[str]:
    """The first title the item's call-up prints: a motion's or report's
    title line, the topic of an Aktuelle Stunde or a Regierungserklärung, or
    a bill's name."""
    lines = [(p.get("klasse"), _text(p)) for p in top.findall("p")]
    titles = [
        text
        for kind, text in lines
        if kind == _TITLE_LINE and text and not text.startswith("Drucksache")
    ]
    for kind, text in lines:
        if kind in _ITEM_TEXT and text.startswith("Abgabe einer Regierungserklärung"):
            return f"Regierungserklärung: {titles[0]}" if titles else None
        if kind in _ITEM_TEXT and (bill := _bill_title(text)):
            return bill
        if kind != _TITLE_LINE or text not in titles:
            continue
        if text == "Aktuelle Stunde" and len(titles) > 1:
            return f"Aktuelle Stunde: {titles[1]}"
        if text.startswith("Sammelübersicht") and len(titles) > 1:
            return "Sammelübersichten zu Petitionen"
        return text
    return None


def _agenda_titles(root: Any) -> dict[str, str]:
    titles: dict[str, str] = {}
    for top in root.iter("tagesordnungspunkt"):
        # A joint debate ("Tagesordnungspunkt 8 und Zusatzpunkt 4") is filed
        # under its first item, as its DIP speeches are.
        slug = agenda_slug_from_top_id(top.get("top-id"))
        if slug and slug not in titles and (title := _item_title(top)):
            titles[slug] = title
    return titles


def _agenda_documents(root: Any) -> dict[str, list[str]]:
    """An item can be called up more than once (debate, then the votes), and
    a joint debate is filed under its first item, as with the titles."""
    lines: dict[str, list[str]] = {}
    for top in root.iter("tagesordnungspunkt"):
        slug = agenda_slug_from_top_id(top.get("top-id"))
        if not slug:
            continue
        lines.setdefault(slug, []).extend(
            _text(p) for p in top.findall("p") if p.get("klasse") == _DOCUMENT_LINE
        )
    return {slug: drucksachen_in_text(" ".join(text)) for slug, text in lines.items()}


def count_interjections(comment: str) -> int:
    reactions = _REACTION_SEPARATOR.split(comment.strip().strip("()").strip())
    return sum(1 for r in reactions if _CONFLICT_REACTION.match(r))


def _interjections_by_speech(root: Any) -> dict[str, int]:
    return {
        str(rede.get("id")): sum(
            count_interjections(_text(k)) for k in rede.iter("kommentar")
        )
        for rede in root.iter("rede")
        if rede.get("id")
    }


def protocol_index(xml_text: str) -> ProtocolIndex:
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        root = None
    index = ProtocolIndex(
        session_date=_session_date(root) if root is not None else None,
        titles=_agenda_titles(root) if root is not None else {},
        documents=_agenda_documents(root) if root is not None else {},
    )
    interjections = _interjections_by_speech(root) if root is not None else {}
    for position, speech in enumerate(parse_speeches_from_xml(xml_text)):
        printed = str(speech.get("source_page") or "")
        index.speeches.append(
            ProtocolSpeech(
                position=position,
                printed_page=int(printed) if printed.isdigit() else None,
                speaker=slugify_speaker(full_name=speech.get("speaker_name") or ""),
                agenda=agenda_slug_from_top_id(speech.get("agenda_top_id")),
                interjections=interjections.get(str(speech.get("xml_rede_id")), 0),
            )
        )
    return index


def speaker_slug(speech: Speech) -> str:
    """The speaker part of the speech_key, or the name slugged the same way
    when the key has none."""
    match = _KEY_SPEAKER_RE.match(speech.speech_key or "")
    if match and match.group(1):
        return match.group(1)
    return slugify_speaker(full_name=speech.speaker or "")


def _match_item(item: AgendaItem, index: ProtocolIndex) -> dict[str, ProtocolSpeech]:
    """source_item_id -> the protocol speech it is. A speaker who takes the
    floor twice under one item takes their places in order."""
    taken: set[int] = set()
    matched: dict[str, ProtocolSpeech] = {}

    def take(speech: Speech, agenda: str) -> bool:
        speaker = speaker_slug(speech)
        found = next(
            (
                p
                for p in index.speeches
                if p.speaker == speaker
                and p.agenda == agenda
                and p.position not in taken
            ),
            None,
        )
        if found is None:
            return False
        taken.add(found.position)
        matched[speech.source_item_id] = found
        return True

    unmatched = [s for s in item.speeches if not take(s, item.slug)]
    if not unmatched:
        return matched
    # The protocol files this debate under another item: the block where the
    # most of the remaining speakers spoke. Distinct speakers, not speeches,
    # or the Befragung, where the same members ask many questions, would win.
    speakers = {speaker_slug(s) for s in unmatched}
    in_block: dict[str, set[str]] = {}
    for p in index.speeches:
        if p.speaker in speakers:
            in_block.setdefault(p.agenda, set()).add(p.speaker)
    if in_block:
        block = max(in_block, key=lambda agenda: len(in_block[agenda]))
        for speech in unmatched:
            take(speech, block)
    return matched


def _drop_twins(
    items: list[AgendaItem], matches: dict[str, ProtocolSpeech]
) -> set[str]:
    """source_item_ids of speeches that are another speech's twin from the
    other source: same protocol speech, the openparliament.tv one wins."""
    by_position: dict[int, list[Speech]] = {}
    for item in items:
        for speech in item.speeches:
            if (found := matches.get(speech.source_item_id)) is not None:
                by_position.setdefault(found.position, []).append(speech)
    dropped: set[str] = set()
    for twins in by_position.values():
        if len(twins) < 2:
            continue
        keep = next((s for s in twins if s.source == "op"), twins[0])
        dropped.update(s.source_item_id for s in twins if s is not keep)
    return dropped


@dataclass(frozen=True)
class _PdfPlacement:
    pdf: ProtocolPdf
    base_url: str

    def anchor(self, speech: Speech, found: Optional[ProtocolSpeech]) -> None:
        """Link the speech to its first page, and let it find the page of
        any of its sentences: searched from that page on, or through the
        whole PDF for a speech the protocol could not place."""
        first = (
            self.pdf.page(found.printed_page) if found and found.printed_page else None
        )
        speech.protocol_page_url = f"{self.base_url}#page={first}" if first else None
        pdf = self.pdf
        speech.page_of = lambda sentence: pdf.page_of(sentence, first or 1)


def _order(
    speeches: list[Speech],
    matches: dict[str, ProtocolSpeech],
    placement: Optional[_PdfPlacement],
) -> list[Speech]:
    """Protocol order, page anchors set, a DIP speech's own included. A
    speech the protocol does not list goes last, in the stable order it came
    in."""
    placed: list[tuple[int, Speech]] = []
    unplaced: list[Speech] = []
    for speech in speeches:
        found = matches.get(speech.source_item_id)
        if placement is not None:
            placement.anchor(speech, found)
        else:
            speech.protocol_page_url = None
        if found is None:
            unplaced.append(speech)
            continue
        placed.append((found.position, speech))
    if unplaced:
        logger.warning(
            "%d speech(es) not found in protocol %s: %s",
            len(unplaced),
            placement.base_url if placement else "",
            [s.speech_key for s in unplaced],
        )
    return [s for _, s in sorted(placed, key=lambda p: p[0])] + unplaced


def _placement(
    read: ReadPdf, pdf_url: str, protocol_id: str
) -> Optional[_PdfPlacement]:
    try:
        pdf = read(pdf_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No PDF pages for %s: %s", protocol_id, exc)
        return None
    return _PdfPlacement(pdf, pdf_url)


def apply_protocols(
    sitting: SittingDay,
    fetch: FetchText = fetch_text,
    read_pdf: Optional[ReadPdf] = None,
) -> int:
    """Put each agenda item's speeches into protocol order, link them to their
    protocol page, drop the twin of a speech both sources hold, title the
    items no source titled and note each item's Drucksachen and interjections;
    returns how many agenda items are now ordered.

    An item whose protocol XML or PDF cannot be read stays unordered, and the
    builder leaves it for a later run.
    """
    ordered = 0
    for protocol_id, pdf_url in sitting.protocols:
        match = _PROTOCOL_ID_RE.match(protocol_id)
        xml_url = protocol_xml_url(pdf_url) if pdf_url else None
        if not match or not xml_url:
            continue
        session = (int(match.group(1)), int(match.group(2)))
        try:
            index = protocol_index(fetch(xml_url))
        except Exception as exc:  # noqa: BLE001
            logger.warning("No protocol order for %s: %s", protocol_id, exc)
            continue
        if not index.speeches:
            logger.warning("Protocol %s lists no speeches yet", protocol_id)
            continue
        if index.session_date and index.session_date != sitting.day:
            logger.warning(
                "Protocol %s is dated %s, its speeches %s",
                protocol_id,
                index.session_date,
                sitting.day,
            )
        items = [i for i in sitting.agenda_items if i.session == session]
        matches: dict[str, ProtocolSpeech] = {}
        for item in items:
            matches.update(_match_item(item, index))
        twins = _drop_twins(items, matches)
        for item in items:
            if item.label == numbered_label(item.slug) and item.slug in index.titles:
                item.label = index.titles[item.slug]
            item.drucksachen = index.documents.get(item.slug, [])
        pdf_base = xml_url[: -len(".xml")] + ".pdf"
        placement = _placement(read_pdf or read_protocol_pdf, pdf_base, protocol_id)
        for item in items:
            item.speeches = _order(
                [s for s in item.speeches if s.source_item_id not in twins],
                matches,
                placement,
            )
            item.ordered = placement is not None
            # Summed over the item's own speeches, so a debate the protocol
            # files under another item still gets its own count.
            item.interjections = sum(
                matches[s.source_item_id].interjections
                for s in item.speeches
                if s.source_item_id in matches
            )
            if item.speeches and not any(
                s.source_item_id in matches for s in item.speeches
            ):
                # The protocol lists none of it: no debate the protocol knows
                # (e.g. the chair's remarks filed as speeches), so no item.
                logger.warning(
                    "%s (%s) is not in protocol %s; left out",
                    item.label,
                    item.key,
                    protocol_id,
                )
                item.speeches = []
            ordered += bool(item.speeches) and item.ordered
        sitting.agenda_items = [i for i in sitting.agenda_items if i.speeches]
    return ordered
