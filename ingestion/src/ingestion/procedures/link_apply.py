# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Write procedure links onto vote and speech chunks, payload only.

Selects every Bundestag vote and speech chunk without a ``procedure_link``
(new, or rewritten by its connector since), plus recent ones linked to
nothing (DIP tags protocols with a delay), resolves them, and sets
``vorgang_ids``, ``sachgebiete`` and ``procedure_link`` on their exact point
ids. Vectors are never touched. A vote or protocol whose DIP read fails is
left unstamped and picked up again next run.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from qdrant_client import QdrantClient, models

from ingestion.procedures.dip import DipReader
from ingestion.procedures.link_speeches import Speech, resolve_protocol
from ingestion.procedures.link_votes import resolve_vote, totals_of
from wahlchat_common.procedures import LinkMethod, ProcedureRecord

logger = logging.getLogger(__name__)

RECHECK_DAYS = 14
_SCROLL_PAGE = 1024
_WRITE_BATCH = 256
_LINK_FIELDS = [
    "source_type",
    "source",
    "source_item_id",
    "speech_key",
    "publish_date",
    "wahlperiode",
    "region",
    "meta",
    "vorgang_ids",
    "procedure_link",
]


@dataclass
class LinkReport:
    methods: Counter[str] = field(default_factory=Counter)
    chunks_written: int = 0
    failed: list[str] = field(default_factory=list)
    missing_procedures: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _Item:
    """One vote or speech: its chunks' point ids and the payload of one."""

    point_ids: tuple[str, ...]
    payload: dict[str, Any]


def _needs_link(today: date) -> models.Filter:
    recent = datetime.combine(today - timedelta(days=RECHECK_DAYS), time(), tzinfo=timezone.utc)
    return models.Filter(
        should=[
            models.IsEmptyCondition(is_empty=models.PayloadField(key="procedure_link")),
            models.Filter(
                must=[
                    models.FieldCondition(
                        key="procedure_link.method", match=models.MatchValue(value="none")
                    ),
                    models.FieldCondition(
                        key="publish_date", range=models.DatetimeRange(gte=recent)
                    ),
                ]
            ),
        ]
    )


def _scroll(qdrant: QdrantClient, collection: str, flt: models.Filter) -> Iterator[Any]:
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=flt,
            limit=_SCROLL_PAGE,
            offset=offset,
            with_payload=_LINK_FIELDS,
            with_vectors=False,
        )
        yield from points
        if offset is None:
            return


def _items(points: Iterable[Any]) -> list[_Item]:
    """Chunks grouped by source item (one vote, one speech)."""
    ids: dict[str, list[str]] = defaultdict(list)
    first: dict[str, dict[str, Any]] = {}
    for point in points:
        payload = point.payload or {}
        key = str(payload.get("source_item_id"))
        ids[key].append(str(point.id))
        first.setdefault(key, payload)
    return [_Item(tuple(sorted(ids[k])), first[k]) for k in sorted(ids)]


def _base(source_type: str, wahlperioden: list[int]) -> list[Any]:
    return [
        models.FieldCondition(key="source_type", match=models.MatchValue(value=source_type)),
        models.FieldCondition(key="wahlperiode", match=models.MatchAny(any=wahlperioden)),
    ]


def _day(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def protocol_of(speech_key: Optional[str]) -> Optional[str]:
    """'de-21-91-stefan-seidler-top12' → '21/91'."""
    parts = (speech_key or "").split("-")
    if len(parts) < 3 or parts[0] != "de" or not (parts[1].isdigit() and parts[2].isdigit()):
        return None
    return f"{parts[1]}/{parts[2]}"


class Linker:
    """Resolves links against the stored procedures and writes them."""

    def __init__(
        self,
        *,
        dip: DipReader,
        qdrant: QdrantClient,
        collection: str,
        procedures: dict[str, ProcedureRecord],
        today: date,
        add_procedures: Optional[Callable[[set[str]], dict[str, ProcedureRecord]]] = None,
        dry_run: bool = False,
    ) -> None:
        self._dip = dip
        self._qdrant = qdrant
        self._collection = collection
        self._procedures = procedures
        self._today = today
        self._add_procedures = add_procedures
        self._dry_run = dry_run
        self.report = LinkReport()
        self._tried: set[str] = set()
        self._pending: dict[tuple[tuple[str, ...], tuple[str, ...], str], list[str]] = defaultdict(list)

    # -- shared --------------------------------------------------------

    def _known(self, ids: Iterable[str]) -> list[str]:
        """Only stored procedures; unknown ids are synced once if in scope."""
        wanted = set(ids)
        missing = wanted - set(self._procedures)
        untried = missing - self._tried
        if untried and self._add_procedures is not None:
            self._tried |= untried
            self._procedures.update(self._add_procedures(untried))
            missing = wanted - set(self._procedures)
        self.report.missing_procedures |= missing
        return sorted(wanted & set(self._procedures))

    def _stamp(self, item: _Item, vorgang_ids: list[str], method: LinkMethod) -> None:
        known = self._known(vorgang_ids)
        if vorgang_ids and not known:
            method = "out_of_scope"
        sachgebiete = sorted({s for vid in known for s in self._procedures[vid].sachgebiete})
        self.report.methods[method] += 1
        key = (tuple(known), tuple(sachgebiete), method)
        self._pending[key].extend(item.point_ids)

    def flush(self) -> None:
        for (vorgang_ids, sachgebiete, method), point_ids in self._pending.items():
            payload = {
                "vorgang_ids": list(vorgang_ids),
                "sachgebiete": list(sachgebiete),
                "procedure_link": {"method": method, "checked_on": self._today.isoformat()},
            }
            for start in range(0, len(point_ids), _WRITE_BATCH):
                batch = point_ids[start : start + _WRITE_BATCH]
                if not self._dry_run:
                    self._qdrant.set_payload(
                        collection_name=self._collection,
                        payload=payload,
                        points=models.PointIdsList(points=list(batch)),
                        wait=True,
                    )
                self.report.chunks_written += len(batch)
        self._pending.clear()

    # -- votes ---------------------------------------------------------

    def link_votes(self, wahlperioden: list[int]) -> None:
        flt = models.Filter(
            must=[
                *_base("vote_record", wahlperioden),
                models.FieldCondition(key="region", match=models.MatchValue(value="DE")),
                _needs_link(self._today),
            ]
        )
        days: dict[date, list[dict[str, Any]]] = {}

        def positions_on(day: date) -> list[dict[str, Any]]:
            if day not in days:
                days[day] = self._dip.positions_on(day)
            return days[day]

        for item in _items(_scroll(self._qdrant, self._collection, flt)):
            meta = item.payload.get("meta") or {}
            voted_on = _day(item.payload.get("publish_date"))
            if voted_on is None:
                continue
            try:
                result = resolve_vote(
                    voted_on=voted_on,
                    totals=totals_of(meta.get("vote_results") or []),
                    drucksachen=list(meta.get("drucksachen") or []),
                    positions_on=positions_on,
                    drucksache_vorgaenge=self._dip.drucksache_vorgaenge,
                )
            except Exception:  # noqa: BLE001 — left unstamped, retried next run
                logger.exception("Vote %s: DIP read failed", item.payload.get("source_item_id"))
                self.report.failed.append(str(item.payload.get("source_item_id")))
                continue
            self._stamp(item, result.vorgang_ids, result.method)
        self.flush()

    # -- speeches ------------------------------------------------------

    def link_speeches(self, wahlperioden: list[int]) -> None:
        flt = models.Filter(
            must=[*_base("parliamentary_speech", wahlperioden), _needs_link(self._today)]
        )
        dates: set[date] = set()
        protocols: set[str] = set()
        for point in _scroll(self._qdrant, self._collection, flt):
            payload = point.payload or {}
            protocol = protocol_of(payload.get("speech_key"))
            day = _day(payload.get("publish_date"))
            if protocol and day:
                protocols.add(protocol)
                dates.add(day)
        for day in sorted(dates):
            self._link_day(day, protocols, wahlperioden)
            self.flush()

    def _link_day(self, day: date, protocols: set[str], wahlperioden: list[int]) -> None:
        """All speeches of the day: a speaker's order needs every one of them."""
        start = datetime.combine(day, time(), tzinfo=timezone.utc)
        flt = models.Filter(
            must=[
                *_base("parliamentary_speech", wahlperioden),
                models.FieldCondition(
                    key="publish_date",
                    range=models.DatetimeRange(gte=start, lt=start + timedelta(days=1)),
                ),
            ]
        )
        by_protocol: dict[str, list[_Item]] = defaultdict(list)
        for item in _items(_scroll(self._qdrant, self._collection, flt)):
            protocol = protocol_of(item.payload.get("speech_key"))
            if protocol in protocols:
                by_protocol[protocol].append(item)
        for protocol, items in sorted(by_protocol.items()):
            try:
                activities = self._dip.protocol_activities(protocol)
            except Exception:  # noqa: BLE001 — left unstamped, retried next run
                logger.exception("Protocol %s: DIP activities failed", protocol)
                self.report.failed.append(protocol)
                continue
            speeches = [_speech(item) for item in items]
            results = resolve_protocol(speeches, activities)
            for item in items:
                if not _needs_stamp(item.payload, self._today):
                    continue
                result = results[str(item.payload.get("source_item_id"))]
                self._stamp(item, result.vorgang_ids, result.method)

    # -- topics and flags ----------------------------------------------

    def refresh_sachgebiete(self, changed: Iterable[str]) -> None:
        """Re-derive inherited Sachgebiete where a procedure's topics changed."""
        ids = sorted(set(changed))
        if not ids:
            return
        flt = models.Filter(
            must=[
                models.FieldCondition(key="vorgang_ids", match=models.MatchAny(any=ids)),
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchAny(any=["vote_record", "parliamentary_speech"]),
                ),
            ]
        )
        for item in _items(_scroll(self._qdrant, self._collection, flt)):
            link = item.payload.get("procedure_link") or {}
            self._stamp(item, list(item.payload.get("vorgang_ids") or []), link.get("method", "none"))
        self.flush()


def _speech(item: _Item) -> Speech:
    payload = item.payload
    meta = payload.get("meta") or {}
    source = str(payload.get("source") or "dip")
    page = order = None
    if source == "dip":
        page = _int(meta.get("source_page"))
    else:
        order = _int(meta.get("origin_media_id"))
    return Speech(
        key=str(payload.get("source_item_id")),
        source=source,
        speaker_name=str(meta.get("speaker_name") or ""),
        page=page,
        order=order,
    )


def _int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _needs_stamp(payload: dict[str, Any], today: date) -> bool:
    link = payload.get("procedure_link")
    if not link:
        return True
    if link.get("method") != "none":
        return False
    day = _day(payload.get("publish_date"))
    return day is not None and day >= today - timedelta(days=RECHECK_DAYS)


def linked_procedure_ids(qdrant: QdrantClient, collection: str) -> set[str]:
    """Procedures some vote or speech points to (Qdrant facet over the index)."""
    result = qdrant.facet(
        collection_name=collection,
        key="vorgang_ids",
        facet_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchAny(any=["vote_record", "parliamentary_speech"]),
                )
            ]
        ),
        limit=1_000_000,
        exact=True,
    )
    return {str(hit.value) for hit in result.hits}
