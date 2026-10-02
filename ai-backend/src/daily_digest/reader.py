# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Date-window reads over the corpus, and speech chunks rebuilt into sitting days.

Everything here is a filtered ``scroll`` — no vector search, since a digest
wants "everything on day X", not "the closest matches". ``source_type``,
``region`` and ``publish_date`` are all payload-indexed.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from qdrant_client import QdrantClient, models

from src.ingestion.retrieve import dedup_prefer_op

VOTE_SOURCE_TYPE = "vote_record"
SPEECH_SOURCE_TYPE = "parliamentary_speech"

_SCROLL_PAGE = 1000

# de-{ep}-{session}-{speaker_slug}-{agenda_slug}; the agenda slug is empty for
# speeches outside any agenda item, so the key may end in a bare "-".
_SPEECH_KEY_RE = re.compile(r"^de-(\d+)-(\d+)-.*-((?:top|zp)\d+)?$")


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def window_filter(
    source_type: str, region: str, start: date, end: date
) -> models.Filter:
    """``source_type`` + ``region`` + inclusive ``[start, end]`` day window."""
    return models.Filter(
        must=[
            models.FieldCondition(
                key="source_type", match=models.MatchValue(value=source_type)
            ),
            models.FieldCondition(key="region", match=models.MatchValue(value=region)),
            models.FieldCondition(
                key="publish_date",
                range=models.DatetimeRange(
                    gte=_day_start(start), lt=_day_start(end + timedelta(days=1))
                ),
            ),
        ]
    )


def scroll_payloads(
    client: QdrantClient, collection: str, scroll_filter: models.Filter
) -> list[dict]:
    payloads: list[dict] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=_SCROLL_PAGE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        payloads.extend(p.payload or {} for p in points)
        if offset is None:
            return payloads


def latest_publish_date(
    client: QdrantClient, collection: str, source_types: list[str], region: str
) -> Optional[date]:
    """Most recent ``publish_date`` across ``source_types`` in ``region``."""
    latest: Optional[date] = None
    for source_type in source_types:
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_type", match=models.MatchValue(value=source_type)
                    ),
                    models.FieldCondition(
                        key="region", match=models.MatchValue(value=region)
                    ),
                ]
            ),
            limit=1,
            order_by=models.OrderBy(
                key="publish_date", direction=models.Direction.DESC
            ),
            with_payload=["publish_date"],
            with_vectors=False,
        )
        for point in points:
            found = parse_day((point.payload or {}).get("publish_date"))
            if found and (latest is None or found > latest):
                latest = found
    return latest


def compute_window(latest: date, days: int) -> tuple[date, date]:
    """The ``days``-long inclusive window that ends on ``latest``."""
    if days < 1:
        raise ValueError("days must be >= 1")
    return latest - timedelta(days=days - 1), latest


def parse_day(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Speeches → sitting days
# ---------------------------------------------------------------------------


@dataclass
class Speech:
    source_item_id: str
    source: Optional[str]
    day: date
    speaker: str
    party_id: str
    text: str
    citation_title: Optional[str]
    citation_url: Optional[str]
    agenda_slug: str
    agenda_title: Optional[str]
    agenda_official: Optional[str]
    video_uri: Optional[str]
    protocol_id: Optional[str]
    pdf_url: Optional[str]
    session_key: Optional[tuple[int, int]]
    speech_key: Optional[str] = None
    # The protocol PDF opened at this speech's page. DIP speeches carry it in
    # their citation; for the others protocol_pages.attach_protocol_pages
    # looks it up in the protocol XML.
    protocol_page_url: Optional[str] = None
    content_hashes: list[str] = field(default_factory=list)


@dataclass
class AgendaItem:
    key: str
    label: str
    speeches: list[Speech]

    @property
    def video_url(self) -> Optional[str]:
        return next((s.video_uri for s in self.speeches if s.video_uri), None)


@dataclass
class SittingDay:
    day: date
    protocols: list[tuple[str, Optional[str]]]
    agenda_items: list[AgendaItem]

    @property
    def content_hashes(self) -> list[str]:
        return sorted(
            h
            for item in self.agenda_items
            for s in item.speeches
            for h in s.content_hashes
        )


def parse_speech_key(key: Optional[str]) -> tuple[Optional[tuple[int, int]], str]:
    """``(ep, session)`` and the agenda slug from a speech_key."""
    if not key:
        return None, ""
    match = _SPEECH_KEY_RE.match(key)
    if not match:
        return None, ""
    return (int(match.group(1)), int(match.group(2))), match.group(3) or ""


def _strip_fragment(url: Optional[str]) -> Optional[str]:
    return url.split("#", 1)[0] if url else None


def _speech_from_chunks(chunks: list[dict]) -> Optional[Speech]:
    chunks = sorted(chunks, key=lambda c: c.get("chunk_index") or 0)
    head = chunks[0]
    day = parse_day(head.get("publish_date"))
    if day is None:
        return None
    meta = head.get("meta") or {}
    session_key, agenda_slug = parse_speech_key(head.get("speech_key"))
    is_dip = head.get("source") == "dip"
    return Speech(
        source_item_id=str(head.get("source_item_id")),
        source=head.get("source"),
        day=day,
        speaker=str(meta.get("speaker_name") or ""),
        party_id=str(head.get("party_id") or "unbekannt"),
        text=" ".join(str(c.get("text") or "") for c in chunks).strip(),
        citation_title=head.get("citation_title"),
        citation_url=head.get("citation_url"),
        agenda_slug=agenda_slug,
        agenda_title=meta.get("agenda_item_title"),
        agenda_official=meta.get("agenda_item_official"),
        video_uri=meta.get("video_uri"),
        protocol_id=meta.get("protocol_id"),
        pdf_url=_strip_fragment(head.get("citation_url"))
        if is_dip
        else meta.get("transcript_pdf_url"),
        session_key=session_key,
        speech_key=head.get("speech_key"),
        protocol_page_url=(
            head.get("citation_url")
            if is_dip and "#page=" in str(head.get("citation_url") or "")
            else None
        ),
        content_hashes=[str(c.get("content_hash") or "") for c in chunks],
    )


def assemble_speeches(payloads: list[dict]) -> list[Speech]:
    """Rejoin chunked speeches and drop DIP twins of openparliament.tv speeches."""
    by_item: "OrderedDict[str, list[dict]]" = OrderedDict()
    for payload in dedup_prefer_op(payloads):
        by_item.setdefault(str(payload.get("source_item_id")), []).append(payload)
    speeches = [_speech_from_chunks(chunks) for chunks in by_item.values()]
    return [s for s in speeches if s is not None and s.text]


def _agenda_label(slug: str, speeches: list[Speech]) -> str:
    title = next((s.agenda_title for s in speeches if s.agenda_title), None)
    if title:
        return title
    official = next((s.agenda_official for s in speeches if s.agenda_official), None)
    if official:
        return official
    match = re.match(r"(top|zp)(\d+)$", slug)
    if match:
        kind = "Tagesordnungspunkt" if match.group(1) == "top" else "Zusatzpunkt"
        return f"{kind} {match.group(2)}"
    return "Sonstige Wortbeiträge"


def _agenda_sort_key(slug: str) -> tuple[int, int]:
    match = re.match(r"(top|zp)(\d+)$", slug)
    if not match:
        return (2, 0)
    return (0 if match.group(1) == "top" else 1, int(match.group(2)))


def _protocols(speeches: list[Speech]) -> list[tuple[str, Optional[str]]]:
    found: "OrderedDict[str, Optional[str]]" = OrderedDict()
    for s in speeches:
        protocol_id = s.protocol_id or (
            f"{s.session_key[0]}/{s.session_key[1]}" if s.session_key else None
        )
        if protocol_id is None:
            continue
        if found.get(protocol_id) is None:
            found[protocol_id] = s.pdf_url
    return list(found.items())


def group_sitting_days(speeches: list[Speech]) -> dict[date, SittingDay]:
    """Speeches by day, then by agenda item in agenda order."""
    by_day: dict[date, list[Speech]] = {}
    for speech in speeches:
        by_day.setdefault(speech.day, []).append(speech)

    days: dict[date, SittingDay] = {}
    for day, day_speeches in sorted(by_day.items()):
        by_slug: "OrderedDict[str, list[Speech]]" = OrderedDict()
        for speech in day_speeches:
            session = speech.session_key[1] if speech.session_key else 0
            by_slug.setdefault(f"{session}:{speech.agenda_slug}", []).append(speech)
        items = [
            AgendaItem(
                key=key,
                label=_agenda_label(key.split(":", 1)[1], group),
                speeches=group,
            )
            for key, group in sorted(
                by_slug.items(),
                key=lambda kv: (
                    kv[0].split(":", 1)[0].zfill(6),
                    _agenda_sort_key(kv[0].split(":", 1)[1]),
                ),
            )
        ]
        days[day] = SittingDay(
            day=day, protocols=_protocols(day_speeches), agenda_items=items
        )
    return days
