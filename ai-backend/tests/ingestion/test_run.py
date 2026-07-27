# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
run_connector / get_cursor behaviour tests.

Covers the source-scoped cursor (op and DIP keep ISOLATED `max(external_id)`
cursors despite sharing source_type "parliamentary_speech"), the batch-window
stall guard, and the full-parent-footprint orphan reconciliation.
"""

from __future__ import annotations

import types
from datetime import date
from typing import Optional
from unittest.mock import MagicMock

from src.ingestion.connector import BaseConnector
from src.ingestion.ids import (
    compute_chunk_id,
    compute_source_item_id,
    make_chunk_key,
)
from src.ingestion.run import get_cursor, run_connector
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType


class _CursorQdrant:
    """Fake Qdrant recording the scroll_filter and returning a per-source max."""

    def __init__(self, by_source: dict[str, int]) -> None:
        self._by_source = by_source
        self.last_filter = None

    def scroll(
        self,
        *,
        collection_name,
        scroll_filter,
        order_by,
        limit,
        with_payload,
        with_vectors,
    ):  # noqa: ANN001, ANN003
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
    """op vs dip max(external_id) is isolated by the `source` param."""
    qdrant = _CursorQdrant({"op": 20230601, "dip": 20260615})

    op_cursor = get_cursor(
        qdrant, "wahlchat_chunks_dev", "parliamentary_speech", source="op"
    )
    dip_cursor = get_cursor(
        qdrant, "wahlchat_chunks_dev", "parliamentary_speech", source="dip"
    )

    assert op_cursor == 20230601, f"op cursor must be isolated; got {op_cursor}"
    assert dip_cursor == 20260615, f"dip cursor must be isolated; got {dip_cursor}"
    assert op_cursor != dip_cursor, "op and dip cursors must not cross-pollinate"

    # The scroll filter for a source-scoped call carries a `source` FieldCondition.
    must_keys = {getattr(c, "key", None) for c in (qdrant.last_filter.must or [])}
    assert "source" in must_keys and "source_type" in must_keys


class _CursorFilterRecorder:
    """Fake Qdrant recording the scroll_filter of every order_by (cursor) scroll."""

    def __init__(self) -> None:
        self.cursor_filters: list = []

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        if kwargs.get("order_by") is not None:
            self.cursor_filters.append(kwargs.get("scroll_filter"))
        return ([], None)


def _cursor_filter_keys(flt) -> set:  # noqa: ANN001
    return {getattr(c, "key", None) for c in (getattr(flt, "must", []) or [])}


def test_runner_honors_cursor_source_none() -> None:
    """A connector with cursor_source=None gets an UNSCOPED cursor read even
    though it stamps a `source` — the DIP floor must span both speech sources
    (op supersede-deletes dip points, so a dip-scoped max walks backward)."""
    from unittest.mock import MagicMock as _MM

    class _DipLikeStub(_ChunksStub):
        source: str = "dip"
        cursor_source = None  # class attr shadows the BaseConnector property

    qdrant = _CursorFilterRecorder()
    run_connector(_DipLikeStub({}), qdrant, _MM(), batch_size=1)

    assert qdrant.cursor_filters, "get_cursor must have been consulted"
    assert "source" not in _cursor_filter_keys(qdrant.cursor_filters[0]), (
        "cursor_source=None must drop the source condition from the cursor scroll"
    )


def test_runner_defaults_cursor_source_to_source() -> None:
    """Without an override, the cursor stays scoped to the connector's source
    (op keeps its independent source-scoped cursor)."""
    from unittest.mock import MagicMock as _MM

    class _OpLikeStub(_ChunksStub):
        source: str = "op"

    qdrant = _CursorFilterRecorder()
    run_connector(_OpLikeStub({}), qdrant, _MM(), batch_size=1)

    assert "source" in _cursor_filter_keys(qdrant.cursor_filters[0]), (
        "the BaseConnector default scopes the cursor to the connector's source"
    )


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


def test_base_connector_declares_source_type_contract() -> None:
    """The ABC itself declares the required `source_type` attribute (annotation,
    no default) and the optional `source` discriminator (default None)."""
    assert "source_type" in BaseConnector.__annotations__, (
        "BaseConnector must declare source_type as a documented required attribute"
    )
    assert not hasattr(BaseConnector, "source_type") or isinstance(
        BaseConnector.source_type, str
    ), "source_type must have NO non-str default on the ABC"
    assert BaseConnector.source is None, (
        "the optional source discriminator defaults to None"
    )


class _ChunksStub(BaseConnector):
    """Stub connector returning a pre-baked chunks list per external_id.

    Declares the required `source_type` class attribute (the ABC now documents
    it as mandatory; the runner reads it without a type: ignore)."""

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
        parent_keys: set[str] = set()
        for cond in getattr(flt, "must", []) or []:
            key = getattr(cond, "key", None)
            match = cond.match
            if key == "source_item_id":
                values = getattr(match, "any", None)
                if values is None:
                    values = [getattr(match, "value", None)]
                siids.update(str(v) for v in values)
            elif key == "source_parent_key":
                parent_keys.add(str(getattr(match, "value", None)))
        points = [
            types.SimpleNamespace(id=pid, payload=payload)
            for pid, payload in self.existing.items()
            if str(payload.get("source_item_id")) in siids
            or str(payload.get("source_parent_key")) in parent_keys
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
    assert report.present_skips == 2, (
        "present-and-unchanged items are counted separately"
    )
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


def _deleted_point_ids(delete_call: dict) -> set[str]:
    """Extract the point ids from a PointIdsList delete call."""
    selector = delete_call["points_selector"]
    points = getattr(selector, "points", None)
    assert points is not None, (
        f"delete must use PointIdsList (orphan ids only), got {selector!r}"
    )
    return {str(p) for p in points}


def test_multi_source_item_id_orphan_delete() -> None:
    """(c) An item whose chunks span source_item_ids A and B must delete the
    orphan under siid B — and ONLY that orphan (PointIdsList of
    existing − new; surviving ids are overwritten in place by the upsert)."""
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

    assert len(qdrant.deletes) == 1, "orphan cleanup must delete the stale point"
    assert _deleted_point_ids(qdrant.deletes[0]) == {orphan_pid}, (
        "ONLY the orphan point id may be deleted — never the whole footprint"
    )
    assert len(qdrant.upserts) == 1
    assert report.chunks_upserted == 2


def test_disappeared_child_reconciled_via_parent_footprint() -> None:
    """(c) A child that vanishes ENTIRELY from a multi-child parent must be deleted.

    Parent p1 previously produced speeches A+B; the new normalize() yields ONLY A.
    B's source_item_id appears in no new chunk, so a source_item_id-only footprint
    would never scan it and B would stay retrievable forever. The parent-scoped
    scope (source_parent_key) sees the full old footprint and deletes B."""
    chunk_a = _chunk("speech-A", 0, "Rede A", content_hash="h-a")
    chunk_b = _chunk("speech-B", 0, "Rede B", content_hash="h-b")

    # Prior run ingested BOTH A and B under parent p1 (runner stamps this key).
    parent_key = "vote_record:p1"
    existing = {}
    for c in (chunk_a, chunk_b):
        pid = str(compute_chunk_id(c.source_item_id, c.chunk_index))
        existing[pid] = {
            "source_item_id": str(c.source_item_id),
            "content_hash": c.content_hash,
            "source_parent_key": parent_key,
        }

    # New normalize for p1 emits ONLY A — B has disappeared upstream.
    connector = _ChunksStub({"p1": [chunk_a]})
    qdrant = _FootprintQdrant(existing)
    embed = _mock_embed()

    run_connector(connector, qdrant, embed, batch_size=10)

    b_pid = str(compute_chunk_id(chunk_b.source_item_id, 0))
    assert len(qdrant.deletes) == 1, (
        "the vanished child must trigger exactly one delete"
    )
    assert _deleted_point_ids(qdrant.deletes[0]) == {b_pid}, (
        "ONLY B's orphaned point may be deleted; A survives (overwritten in place)"
    )


def test_shrink_in_place_removes_stale_chunk() -> None:
    """(c) An item that previously stored 3 chunks and now yields 2 (all present,
    content unchanged) must STILL take the rewrite branch and delete ONLY the
    stale 3rd chunk's point id so it stops being retrievable."""
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
        "3→2 shrink-in-place must delete the stale chunk_index=2 point"
    )
    assert _deleted_point_ids(qdrant.deletes[0]) == {stale_pid}, (
        "only the orphan id is deleted; the surviving 2 ids are upsert-overwritten"
    )
    assert len(qdrant.upserts) == 1, "the surviving 2 chunks must be re-upserted"
    assert report.chunks_upserted == 2
    assert report.processed == 1
    assert report.present_skips == 0, (
        "an orphaned footprint is NOT a clean present-skip"
    )


def test_rewrite_preserves_grafted_transcript_pdf_url() -> None:
    """Regression: a rewrite (content changed) must carry a previously grafted
    meta.transcript_pdf_url into the new payloads — the fresh mapper output never
    emits it and the donating DIP twin is already deleted, so without this every
    op re-alignment cycle strips the merge result."""
    pdf_url = "https://dserver.bundestag.de/btp/20/2000101.pdf"
    new_chunk = _chunk("speech-G", 0, "neu ausgerichteter Text", content_hash="h-new")
    pid = str(compute_chunk_id(new_chunk.source_item_id, 0))
    existing = {
        pid: {
            "source_item_id": str(new_chunk.source_item_id),
            "content_hash": "h-old",  # content changed → rewrite fires
            "meta": {"transcript_pdf_url": pdf_url},
        }
    }

    connector = _ChunksStub({"g1": [new_chunk]})
    qdrant = _FootprintQdrant(existing)
    embed = _mock_embed()

    run_connector(connector, qdrant, embed, batch_size=10)

    assert len(qdrant.upserts) == 1
    upserted = qdrant.upserts[0]["points"][0]
    assert (upserted.payload.get("meta") or {}).get("transcript_pdf_url") == pdf_url, (
        "the grafted transcript PDF must survive the rewrite"
    )


def test_rewrite_does_not_overwrite_new_chunks_own_pdf() -> None:
    """A new payload that ALREADY carries meta.transcript_pdf_url keeps its
    own value — the preserved graft applies only where the field is absent."""
    own_pdf = "https://dserver.bundestag.de/btp/21/OWN.pdf"
    stale_pdf = "https://dserver.bundestag.de/btp/20/STALE.pdf"
    base = _chunk("speech-H", 0, "Text", content_hash="h-new")
    new_chunk = base.model_copy(update={"meta": {"transcript_pdf_url": own_pdf}})
    pid = str(compute_chunk_id(new_chunk.source_item_id, 0))
    existing = {
        pid: {
            "source_item_id": str(new_chunk.source_item_id),
            "content_hash": "h-old",
            "meta": {"transcript_pdf_url": stale_pdf},
        }
    }

    connector = _ChunksStub({"h1": [new_chunk]})
    qdrant = _FootprintQdrant(existing)
    embed = _mock_embed()

    run_connector(connector, qdrant, embed, batch_size=10)

    upserted = qdrant.upserts[0]["points"][0]
    assert (upserted.payload.get("meta") or {}).get("transcript_pdf_url") == own_pdf


class _SkipReportingStub(_ChunksStub):
    """Stub whose normalize() reports op-superseded skipped siids (plumbing)."""

    def __init__(self, chunks_by_id: dict, superseded_siids: list[str]) -> None:
        super().__init__(chunks_by_id)
        self._superseded_siids = superseded_siids

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        self.last_superseded_siids = tuple(self._superseded_siids)
        return super().normalize(raw)


def test_runner_deletes_stranded_twins_reported_by_normalize() -> None:
    """Mitigation: siids a connector's normalize() skipped as op-superseded
    are cleaned up by the runner — a stranded DIP twin from an interleaved
    concurrent DIP+op run appears in no new-chunk/orphan filter otherwise."""
    stranded_siid = "11111111-2222-3333-4444-555555555555"
    connector = _SkipReportingStub({"p1": []}, [stranded_siid])
    qdrant = _FootprintQdrant({})
    embed = _mock_embed()

    run_connector(connector, qdrant, embed, batch_size=10)

    assert len(qdrant.deletes) == 1, "the stranded twin's siid must be deleted"
    delete_filter = qdrant.deletes[0]["points_selector"].filter
    matched: set[str] = set()
    for cond in delete_filter.must:
        if cond.key == "source_item_id":
            values = getattr(cond.match, "any", None) or [cond.match.value]
            matched.update(str(v) for v in values)
    assert matched == {stranded_siid}
    assert not qdrant.upserts, "an empty-chunks item still upserts nothing"


def test_embed_failure_leaves_existing_footprint_intact() -> None:
    """Loss-window regression: when the embed call fails mid-item, NOTHING may
    have been deleted — the old delete-before-embed order left the item absent
    until (or beyond) lookback expiry."""
    changed = [_chunk("item-C", 0, "korrigierter Text", content_hash="h-new")]
    pid = str(compute_chunk_id(changed[0].source_item_id, 0))
    existing = {
        pid: {
            "source_item_id": str(changed[0].source_item_id),
            "content_hash": "h-old",  # content changed → rewrite branch fires
        }
    }

    connector = _ChunksStub({"c1": changed})
    qdrant = _FootprintQdrant(existing)
    embed = MagicMock()
    embed.embed_documents.side_effect = RuntimeError("OpenAI down")

    # Neutralize tenacity's exponential backoff so the test stays fast.
    from unittest.mock import patch

    with patch(
        "src.ingestion.run._embed_texts", side_effect=RuntimeError("OpenAI down")
    ):
        report = run_connector(connector, qdrant, embed, batch_size=10)

    assert report.failed_ids == ("c1",), "the item is skip-and-warned, not lost"
    assert not qdrant.deletes, "embed must run BEFORE any delete (no loss window)"
    assert not qdrant.upserts


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


def test_dip_resurrection_guard_client_plumbs_api_key(monkeypatch) -> None:
    """(e) The DIP resurrection-guard client forwards QDRANT_API_KEY to QdrantClient
    — behavioural: patch the client constructor and assert the api_key it receives.
    (The run.py __main__ client shares the same wiring but lives in an
    `if __name__ == '__main__'` block, exercised at deploy/integration, not here.)"""
    import qdrant_client

    from src.ingestion.connectors.bundestag_speeches.connector import (
        BundestagSpeechesConnector,
    )

    captured: dict = {}

    class _FakeClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(qdrant_client, "QdrantClient", _FakeClient)
    monkeypatch.setenv("QDRANT_API_KEY", "secret-key")

    conn = BundestagSpeechesConnector.__new__(BundestagSpeechesConnector)
    conn._qdrant = None
    conn._qdrant_lazy_enabled = True  # enable the production lazy-construct path
    conn._get_qdrant()

    assert captured.get("api_key") == "secret-key", (
        "DIP resurrection-guard client must forward QDRANT_API_KEY"
    )
