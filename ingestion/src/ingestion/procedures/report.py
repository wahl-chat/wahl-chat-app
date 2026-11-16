# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""How much of the corpus is linked to procedures, and what is not."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient, models

from wahlchat_common.procedures import ProcedureRecord

UNCHECKED = "unchecked"
_NOT_LINKED = {"none", UNCHECKED}
_FIELDS = ["source_type", "source", "wahlperiode", "region", "source_item_id",
           "procedure_link", "speech_key", "citation_title"]


@dataclass
class Coverage:
    # (wahlperiode, label) → method → items
    methods: dict[tuple[int, str], Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    misses: dict[tuple[int, str], list[str]] = field(default_factory=lambda: defaultdict(list))
    procedures_by_kind: Counter[str] = field(default_factory=Counter)
    linked_by_kind: Counter[str] = field(default_factory=Counter)

    def rate(self, key: tuple[int, str]) -> float:
        """Linked share, among items that could be (out-of-scope excluded)."""
        counts = self.methods[key]
        eligible = sum(n for m, n in counts.items() if m != "out_of_scope")
        linked = sum(n for m, n in counts.items() if m not in _NOT_LINKED | {"out_of_scope"})
        return linked / eligible if eligible else 0.0


def _label(payload: dict[str, Any]) -> str:
    if payload.get("source_type") == "vote_record":
        return "votes"
    return f"speeches/{payload.get('source') or 'dip'}"


def collect(
    points: Iterable[Any], procedures: dict[str, ProcedureRecord], *, max_misses: int = 25
) -> Coverage:
    coverage = Coverage()
    seen: set[str] = set()
    for point in points:
        payload = point.payload or {}
        item = str(payload.get("source_item_id"))
        if item in seen:
            continue
        seen.add(item)
        key = (int(payload.get("wahlperiode") or 0), _label(payload))
        method = (payload.get("procedure_link") or {}).get("method", UNCHECKED)
        coverage.methods[key][method] += 1
        if method in _NOT_LINKED and len(coverage.misses[key]) < max_misses:
            coverage.misses[key].append(
                str(payload.get("speech_key") or payload.get("citation_title") or item)
            )
    for record in procedures.values():
        coverage.procedures_by_kind[record.kind] += 1
        if record.has_links:
            coverage.linked_by_kind[record.kind] += 1
    return coverage


def scroll_linkable(qdrant: QdrantClient, collection: str, wahlperioden: list[int]) -> Iterable[Any]:
    """Bundestag votes and speeches (Landtag votes carry no Wahlperiode)."""
    flt = models.Filter(
        must=[
            models.FieldCondition(key="wahlperiode", match=models.MatchAny(any=wahlperioden)),
            models.FieldCondition(
                key="source_type",
                match=models.MatchAny(any=["vote_record", "parliamentary_speech"]),
            ),
        ],
    )
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=flt,
            limit=2048,
            offset=offset,
            with_payload=_FIELDS,
            with_vectors=False,
        )
        yield from points
        if offset is None:
            return


def render(coverage: Coverage) -> str:
    lines = ["Procedure links (items, not chunks):"]
    for key in sorted(coverage.methods):
        counts = coverage.methods[key]
        total = sum(counts.values())
        mix = ", ".join(f"{m} {n}" for m, n in counts.most_common())
        lines.append(f"  WP {key[0]:>2} {key[1]:<14} {coverage.rate(key):6.1%} linked of {total:>6}  [{mix}]")
    lines.append("Procedures with links, by kind:")
    for kind, total in coverage.procedures_by_kind.most_common():
        lines.append(f"  {kind:<12} {coverage.linked_by_kind[kind]:>5} / {total:>5}")
    for key in sorted(coverage.misses):
        if coverage.misses[key]:
            lines.append(f"Unlinked WP {key[0]} {key[1]} (first {len(coverage.misses[key])}):")
            lines.extend(f"  - {miss}" for miss in coverage.misses[key])
    return "\n".join(lines)
