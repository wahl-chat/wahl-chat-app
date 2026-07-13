# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Source-scoped cursor test for run.get_cursor (D-11/Q2).

`get_cursor` must gain an optional `source` param so op and DIP maintain
ISOLATED `max(external_id)` cursors (both share source_type
"parliamentary_speech"). Without it, op's alignment backlog would drag DIP's
cursor and vice-versa.

Wave-0 SCAFFOLD: the `source` param does not exist yet (11-05). This file
collects cleanly and CAPABILITY-SKIPS (via signature inspection) until the
param lands, then asserts the second FieldCondition scopes the scroll filter.
"""

from __future__ import annotations

import inspect
import types
from datetime import date
from typing import Optional
from unittest.mock import MagicMock

import pytest

from src.ingestion.connector import BaseConnector
from src.ingestion.ids import (
    compute_chunk_id,
    compute_source_item_id,
    make_chunk_key,
)
from src.ingestion.run import get_cursor, run_connector
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

# Capability guard: SKIP until get_cursor accepts a `source` kwarg.
if "source" not in inspect.signature(get_cursor).parameters:
    pytest.skip(
        "get_cursor(source=...) not yet implemented (11-05) — Wave-0 scaffold",
        allow_module_level=True,
    )


class _CursorQdrant:
    """Fake Qdrant recording the scroll_filter and returning a per-source max."""

    def __init__(self, by_source: dict[str, int]) -> None:
        self._by_source = by_source
        self.last_filter = None

    def scroll(self, *, collection_name, scroll_filter, order_by, limit, with_payload, with_vectors):  # noqa: ANN001, ANN003
        self.last_filter = scroll_filter
        # Determine which source the filter scoped to, if any.
        source = None
        for cond in getattr(scroll_filter, "must", []) or []:
            if getattr(cond, "key", None) == "source":
                source = cond.match.value
        ext = self._by_source.get(source)
        if ext is None:
            return ([], None)
        point = types.SimpleNamespace(payload={"external_id": ext})
        return ([point], None)


def test_source_scoped_cursor() -> None:
    """Q2: op vs dip max(external_id) is isolated by the `source` param."""
    qdrant = _CursorQdrant({"op": 20230601, "dip": 20260615})

    op_cursor = get_cursor(qdrant, "wahlchat_chunks_dev", "parliamentary_speech", source="op")
    dip_cursor = get_cursor(qdrant, "wahlchat_chunks_dev", "parliamentary_speech", source="dip")

    assert op_cursor == 20230601, f"op cursor must be isolated; got {op_cursor}"
    assert dip_cursor == 20260615, f"dip cursor must be isolated; got {dip_cursor}"
    assert op_cursor != dip_cursor, "op and dip cursors must not cross-pollinate"

    # The scroll filter for a source-scoped call carries a `source` FieldCondition.
    must_keys = {getattr(c, "key", None) for c in (qdrant.last_filter.must or [])}
    assert "source" in must_keys and "source_type" in must_keys


# ---------------------------------------------------------------------------
# run_connector batch-stall + multi-source_item_id orphan-cleanup regressions
# ---------------------------------------------------------------------------

_DIM = 3072


def _chunk(
    item_id: str,
    chunk_index: int,
    text: str,
    content_hash: Optional[str] = None,
) -> ChunkRecord:
    source_item_id = compute_source_item_id("vote_record", item_id)
    return ChunkRecord(
        chunk_key=make_chunk_key(source_item_id, chunk_index),
        source_item_id=source_item_id,
        chunk_index=chunk_index,
        text=text,
        party_id="spd",
        region="DE",
        authority_tier=AuthorityTier.FACTUAL_RECORD,
        source_type=SourceType.VOTE_RECORD,
        publish_date=date(2024, 1, 15),
        content_hash=content_hash,
    )


class _ChunksStub(BaseConnector):
    """Stub connector returning a pre-baked chunks list per external_id."""

    source_type: str = SourceType.VOTE_RECORD.value

    def __init__(self, chunks_by_id: dict[str, list[ChunkRecord]]) -> None:
        self._chunks_by_id = chunks_by_id

    def discover(self, since: Optional[int]) -> list[str]:
        return sorted(self._chunks_by_id)

    def fetch(self, external_id: str) -> dict:
        return {"external_id": external_id}

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        return self._chunks_by_id[raw["external_id"]]


class _FootprintQdrant:
    """Fake QdrantClient serving BOTH get_cursor's order_by scroll and the
    already-present guard's source_item_id footprint scroll; records deletes."""

    def __init__(self, existing: Optional[dict[str, dict]] = None) -> None:
        # existing: point_id(str) → payload dict with source_item_id (+ content_hash).
        self.existing = dict(existing or {})
        self.deletes: list[dict] = []
        self.upserts: list[dict] = []

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        if kwargs.get("order_by") is not None:
            return ([], None)  # get_cursor → no prior points → since=None
        flt = kwargs.get("scroll_filter")
        siids: set[str] = set()
        for cond in getattr(flt, "must", []) or []:
            if getattr(cond, "key", None) == "source_item_id":
                match = cond.match
                values = getattr(match, "any", None)
                if values is None:
                    values = [getattr(match, "value", None)]
                siids.update(str(v) for v in values)
        points = [
            types.SimpleNamespace(id=pid, payload=payload)
            for pid, payload in self.existing.items()
            if str(payload.get("source_item_id")) in siids
        ]
        return (points, None)

    def delete(self, **kwargs) -> None:  # noqa: ANN003
        self.deletes.append(kwargs)

    def upsert(self, **kwargs) -> None:  # noqa: ANN003
        self.upserts.append(kwargs)


def _mock_embed() -> MagicMock:
    mock = MagicMock()
    mock.embed_documents.side_effect = lambda texts: [[0.0] * _DIM for _ in texts]
    return mock


def _existing_payload(chunk: ChunkRecord) -> tuple[str, dict]:
    pid = str(compute_chunk_id(chunk.source_item_id, chunk.chunk_index))
    return pid, {
        "source_item_id": str(chunk.source_item_id),
        "content_hash": chunk.content_hash,
    }


def test_all_present_first_batch_does_not_stall() -> None:
    """(b) A store where the first N discovered ids are already present must still
    advance to and process new items — present items must not consume the
    batch_size budget (no permanent batch-window stall)."""
    present_a = [_chunk("1", 0, "alt A", content_hash="h-a")]
    present_b = [_chunk("2", 0, "alt B", content_hash="h-b")]
    new_c = [_chunk("3", 0, "neu C", content_hash="h-c")]

    existing: dict[str, dict] = {}
    for c in present_a + present_b:
        pid, payload = _existing_payload(c)
        existing[pid] = payload

    connector = _ChunksStub({"1": present_a, "2": present_b, "3": new_c})
    qdrant = _FootprintQdrant(existing)
    embed = _mock_embed()

    # batch_size=1: under the OLD stall behavior the run would consume its budget
    # on already-present item "1" and NEVER reach "3".
    report = run_connector(connector, qdrant, embed, batch_size=1)

    assert len(qdrant.upserts) == 1, "the NEW item must be reached and upserted"
    assert report.chunks_upserted == 1
    assert report.processed == 1, "only the item that did work counts toward the budget"
    assert report.present_skips == 2, "present-and-unchanged items are counted separately"
    assert report.remaining == 0, "all discovered ids were consumed"


def test_batch_budget_counts_only_worked_items() -> None:
    """(b) batch_size caps the number of items that DO WORK; remaining reflects
    the unconsumed tail of discovered ids."""
    present = [_chunk("1", 0, "alt", content_hash="h-1")]
    new_2 = [_chunk("2", 0, "neu 2", content_hash="h-2")]
    new_3 = [_chunk("3", 0, "neu 3", content_hash="h-3")]
    new_4 = [_chunk("4", 0, "neu 4", content_hash="h-4")]

    pid, payload = _existing_payload(present[0])
    connector = _ChunksStub({"1": present, "2": new_2, "3": new_3, "4": new_4})
    qdrant = _FootprintQdrant({pid: payload})
    embed = _mock_embed()

    report = run_connector(connector, qdrant, embed, batch_size=2)

    assert report.processed == 2, "budget consumed by the two NEW items only"
    assert report.present_skips == 1
    assert len(qdrant.upserts) == 2
    assert report.remaining == 1, "id '4' was never reached → remaining tail is 1"


def test_multi_source_item_id_orphan_delete() -> None:
    """(c) An item whose chunks span source_item_ids A and B must delete orphans
    under BOTH siids before upsert — not just chunks[0]'s."""
    chunk_a = _chunk("speech-A", 0, "Rede A", content_hash="h-a")
    chunk_b = _chunk("speech-B", 0, "Rede B", content_hash="h-b")

    # An orphaned point under siid B (a chunk the new normalize no longer produces).
    orphan_pid = str(compute_chunk_id(chunk_b.source_item_id, 1))
    existing = {
        orphan_pid: {
            "source_item_id": str(chunk_b.source_item_id),
            "content_hash": "h-stale",
        }
    }

    connector = _ChunksStub({"p1": [chunk_a, chunk_b]})
    qdrant = _FootprintQdrant(existing)
    embed = _mock_embed()

    report = run_connector(connector, qdrant, embed, batch_size=10)

    assert len(qdrant.deletes) == 1, "orphan cleanup must delete before upsert"
    delete_filter = qdrant.deletes[0]["points_selector"].filter
    matched: set[str] = set()
    for cond in delete_filter.must:
        if cond.key == "source_item_id":
            values = getattr(cond.match, "any", None) or [cond.match.value]
            matched.update(str(v) for v in values)
    assert str(chunk_a.source_item_id) in matched, "siid A must be covered by the delete"
    assert str(chunk_b.source_item_id) in matched, "siid B (orphan owner) must be covered"
    assert len(qdrant.upserts) == 1
    assert report.chunks_upserted == 2


def test_shrink_in_place_removes_stale_chunk() -> None:
    """(c) An item that previously stored 3 chunks and now yields 2 (all present,
    content unchanged) must STILL take the delete+re-upsert branch so the stale
    3rd chunk stops being retrievable."""
    kept_0 = _chunk("item-S", 0, "Teil 1", content_hash="h-0")
    kept_1 = _chunk("item-S", 1, "Teil 2", content_hash="h-1")
    existing: dict[str, dict] = {}
    for c in (kept_0, kept_1):
        pid, payload = _existing_payload(c)
        existing[pid] = payload
    # The stale 3rd chunk still stored under the SAME source_item_id.
    stale_pid = str(compute_chunk_id(kept_0.source_item_id, 2))
    existing[stale_pid] = {
        "source_item_id": str(kept_0.source_item_id),
        "content_hash": "h-2",
    }

    connector = _ChunksStub({"s1": [kept_0, kept_1]})
    qdrant = _FootprintQdrant(existing)
    embed = _mock_embed()

    report = run_connector(connector, qdrant, embed, batch_size=10)

    assert len(qdrant.deletes) == 1, (
        "3→2 shrink-in-place must delete the item's footprint (stale chunk_index=2)"
    )
    assert len(qdrant.upserts) == 1, "the surviving 2 chunks must be re-upserted"
    assert report.chunks_upserted == 2
    assert report.processed == 1
    assert report.present_skips == 0, "an orphaned footprint is NOT a clean present-skip"


def test_no_orphans_all_present_unchanged_skips() -> None:
    """(c) Control: all present + unchanged + no orphans → clean skip, no delete."""
    kept = [_chunk("item-U", 0, "Teil 1", content_hash="h-u")]
    pid, payload = _existing_payload(kept[0])

    connector = _ChunksStub({"u1": kept})
    qdrant = _FootprintQdrant({pid: payload})
    embed = _mock_embed()

    report = run_connector(connector, qdrant, embed, batch_size=10)

    assert not qdrant.deletes
    assert not qdrant.upserts
    embed.embed_documents.assert_not_called()
    assert report.present_skips == 1
    assert report.processed == 0


# ---------------------------------------------------------------------------
# (e) QDRANT_API_KEY plumbed into every QdrantClient construction
# ---------------------------------------------------------------------------


def test_qdrant_api_key_plumbed_everywhere() -> None:
    """(e) run.py runner, the DIP resurrection-guard client, and
    migrate_speech_key all pass api_key=os.getenv("QDRANT_API_KEY")."""
    import src.ingestion.connectors.bundestag_speeches.connector as dip_mod
    import src.ingestion.connectors.bundestag_speeches.migrate_speech_key as mig_mod
    import src.ingestion.run as run_mod

    needle = 'api_key=os.getenv("QDRANT_API_KEY")'
    assert needle in inspect.getsource(run_mod), "run.py __main__ client must pass api_key"
    assert needle in inspect.getsource(
        dip_mod.BundestagSpeechesConnector._get_qdrant
    ), "DIP resurrection-guard client must pass api_key"
    assert needle in inspect.getsource(mig_mod), "migrate_speech_key client must pass api_key"
