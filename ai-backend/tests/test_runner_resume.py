# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
run_connector() behavioral tests.

StubConnector implements the 3-method ABC (discover/fetch/normalize)
and returns list[ChunkRecord] from normalize(). run_connector() is called with the
3-argument signature (connector, qdrant, embed) — no Firestore.

Tests defined here:
  - test_run_connector_upserts_no_firestore: verifies Qdrant.upsert is
    called and no Firestore client is touched.
  - test_run_connector_dimension_guard_raises: wrong-length vector raises
    ValueError before any Qdrant upsert.
  - test_batch_size_limits_processed: batch_size cap respected.
  - test_time_budget_exits_early: time_budget_s exits the loop gracefully.
  - test_zero_tally_skipped: normalize ValueError causes skip-and-warn, not crash.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.connector import BaseConnector
from src.ingestion.ids import (
    compute_chunk_id,
    compute_source_item_id,
    make_chunk_key,
)
from src.ingestion.run import run_connector
from src.ingestion.schemas import (
    AuthorityTier,
    ChunkRecord,
    SourceType,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMBEDDING_DIM = 3072  # text-embedding-3-large


# ---------------------------------------------------------------------------
# Helper: StubConnector — in-memory 3-method BaseConnector for runner tests.
# ---------------------------------------------------------------------------


def _make_chunk(poll_id: int, chunk_index: int = 0) -> ChunkRecord:
    """Build a minimal ChunkRecord for a given poll_id and chunk_index."""
    source_item_id = compute_source_item_id("vote_record", str(poll_id))
    chunk_key = make_chunk_key(source_item_id, chunk_index)
    return ChunkRecord(
        chunk_key=chunk_key,
        source_item_id=source_item_id,
        chunk_index=chunk_index,
        text=f"Abstimmung {poll_id}: SPD stimmte mit 100 Ja / 0 Nein.",
        party_id="spd",
        region="DE",
        authority_tier=AuthorityTier.FACTUAL_RECORD,
        source_type=SourceType.VOTE_RECORD,
        publish_date=date(2024, 1, poll_id % 28 + 1),
        external_id=poll_id,
    )


class StubConnector(BaseConnector):
    """Minimal in-memory BaseConnector returning list[ChunkRecord] from normalize().

    discover() returns poll_id strings for IDs > since (integer cursor).
    fetch() returns a dict with {"poll_id": int}.
    normalize() returns a list containing one ChunkRecord.
    """

    source_type: str = SourceType.VOTE_RECORD.value

    def __init__(self, poll_ids: list[int]) -> None:
        self._poll_ids = sorted(poll_ids)
        self.fetched: list[str] = []
        self.normalized: list[str] = []

    def discover(self, since: Optional[int]) -> list[str]:
        """Return poll IDs > since, sorted ascending."""
        if since is None:
            return [str(p) for p in self._poll_ids]
        return [str(p) for p in self._poll_ids if p > since]

    def fetch(self, external_id: str) -> dict:
        self.fetched.append(external_id)
        return {"poll_id": int(external_id)}

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        poll_id = raw["poll_id"]
        self.normalized.append(str(poll_id))
        return [_make_chunk(poll_id)]


class ZeroTallyStubConnector(StubConnector):
    """Stub that raises ValueError from normalize() — simulates zero-tally polls."""

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        raise ValueError("zero usable tallies — simulated for test")


class HashStubConnector(StubConnector):
    """Stub whose normalize() stamps a fixed content_hash (for change-detection tests)."""

    def __init__(self, poll_ids: list[int], content_hash: str) -> None:
        super().__init__(poll_ids)
        self._content_hash = content_hash

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        return [
            _make_chunk(raw["poll_id"]).model_copy(
                update={"content_hash": self._content_hash}
            )
        ]


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_mock_qdrant() -> MagicMock:
    """Return a MagicMock for QdrantClient.

    scroll() returns ([], None) so BOTH get_cursor() (order_by scroll) and the
    already-present guard's footprint scroll see nothing → since=None and every
    item takes the embed path in existing tests.
    upsert() is a no-op (MagicMock default).
    """
    mock = MagicMock()
    mock.scroll.return_value = ([], None)
    return mock


def _footprint_scroll(points: list) -> object:
    """Build a scroll side_effect: get_cursor's order_by scroll sees nothing;
    the guard's footprint scroll (no order_by) returns *points* once."""

    def _scroll(**kwargs: object) -> tuple:
        if kwargs.get("order_by") is not None:
            return ([], None)
        return (points, None)

    return _scroll


def _make_mock_embed(dim: int = _EMBEDDING_DIM) -> MagicMock:
    """Return a MagicMock for OpenAIEmbeddings.embed_documents()."""
    mock = MagicMock()
    mock.embed_documents.return_value = [[0.0] * dim]
    return mock


# ---------------------------------------------------------------------------
# no-Firestore + Qdrant upsert called
# ---------------------------------------------------------------------------


def test_run_connector_upserts_no_firestore() -> None:
    """run_connector calls Qdrant.upsert and never touches Firestore.

    Verifies:
      - qdrant.upsert is called at least once (items were actually stored).
      - No Firestore client is constructed or called during the run.
    """
    connector = StubConnector(poll_ids=[100, 200, 300])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    # Patch firestore client construction — should never be called.
    with patch(
        "google.cloud.firestore.Client",
        side_effect=AssertionError("Firestore must not be touched"),
    ) as mock_firestore_cls:
        report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    # Qdrant upsert must have been called for each item.
    assert mock_qdrant.upsert.call_count == 3, (
        f"qdrant.upsert should be called 3 times (one per poll), "
        f"got {mock_qdrant.upsert.call_count}"
    )
    assert report.processed == 3
    # Firestore constructor was never called (patch would have raised AssertionError).
    mock_firestore_cls.assert_not_called()


# ---------------------------------------------------------------------------
# dimension guard raises before upsert
# ---------------------------------------------------------------------------


def test_run_connector_dimension_guard_raises() -> None:
    """wrong-length embedding vector raises ValueError; upsert not called.

    Verifies _upsert_chunks() asserts len(vector) == EMBEDDING_DIM before
    any Qdrant call.  A wrong-length vector must propagate as ValueError and must
    NOT call qdrant.upsert().
    """
    connector = StubConnector(poll_ids=[42])
    mock_qdrant = _make_mock_qdrant()
    # Return a wrong-dimension vector (10 instead of 3072).
    mock_embed = _make_mock_embed(dim=10)

    with pytest.raises(ValueError, match="embedding dim mismatch"):
        run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    # upsert must NOT have been called — dimension guard fires first.
    mock_qdrant.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# batch_size cap
# ---------------------------------------------------------------------------


def test_batch_size_limits_processed() -> None:
    """batch_size=2 processes at most 2 items even if discover returns more."""
    connector = StubConnector(poll_ids=[1, 2, 3, 4, 5])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=2)

    assert report.processed == 2, f"Expected 2 processed, got {report.processed}"
    assert report.remaining == 3, f"Expected 3 remaining, got {report.remaining}"


# ---------------------------------------------------------------------------
# time_budget_s early exit
# ---------------------------------------------------------------------------


def test_time_budget_exits_early() -> None:
    """time_budget_s=0 exits after the first item (budget exceeded immediately)."""
    connector = StubConnector(poll_ids=[10, 20, 30])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    report = run_connector(
        connector, mock_qdrant, mock_embed, batch_size=10, time_budget_s=0.0
    )

    # With time_budget_s=0, the monotonic check fires after the first item.
    assert report.processed >= 1, "At least one item must have been processed"
    assert report.processed <= 3, "Cannot exceed total items"


# ---------------------------------------------------------------------------
# Zero-tally skip-and-warn
# ---------------------------------------------------------------------------


def test_zero_tally_skipped() -> None:
    """normalize() ValueError causes skip-and-warn, not a crash; run completes."""
    connector = ZeroTallyStubConnector(poll_ids=[1, 2, 3])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    # run_connector must NOT propagate the ValueError — it skip-and-warns.
    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    # All items skipped (normalize raises for all), so processed=0.
    assert report.processed == 0, (
        f"All zero-tally items should be skipped (processed=0), got {report.processed}"
    )
    # No upsert was called.
    mock_qdrant.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# Already-present guard: skip embed+upsert when ALL chunk point IDs exist
# ---------------------------------------------------------------------------


def test_already_present_item_skips_embed() -> None:
    """Already-present guard: item whose chunk IDs all exist skips embed/upsert.

    Two-item run: poll 1 (already present), poll 2 (new).
    - embed_documents must be called exactly ONCE (only for poll 2).
    - qdrant.upsert must be called exactly ONCE (only for poll 2).
    - report.processed == 1 (only the item that DID WORK consumes budget).
    - report.present_skips == 1 (poll 1 skipped cheaply).
    - report.chunks_upserted == 1 (only the new item's chunk).
    """
    already_present_poll = 1
    new_poll = 2

    connector = StubConnector(poll_ids=[already_present_poll, new_poll])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    # Compute the point ID for the already-present poll's single chunk (chunk_index=0).
    already_source_item_id = compute_source_item_id(
        "vote_record", str(already_present_poll)
    )
    already_point_id = str(compute_chunk_id(already_source_item_id, 0))

    # Footprint scroll side_effect: serve poll 1's stored point when its
    # source_item_id is in the guard's MatchAny filter; nothing for poll 2.
    def _scroll_side_effect(**kwargs: object) -> tuple:
        if kwargs.get("order_by") is not None:
            return ([], None)  # get_cursor
        flt = kwargs.get("scroll_filter")
        for cond in getattr(flt, "must", []) or []:
            if getattr(cond, "key", None) == "source_item_id":
                values = getattr(cond.match, "any", None) or []
                if str(already_source_item_id) in [str(v) for v in values]:
                    return (
                        [
                            SimpleNamespace(
                                id=already_point_id,
                                payload={"source_item_id": str(already_source_item_id)},
                            )
                        ],
                        None,
                    )
        return ([], None)

    mock_qdrant.scroll.side_effect = _scroll_side_effect

    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    # embed_documents must have been called exactly once — only for the new poll.
    assert mock_embed.embed_documents.call_count == 1, (
        f"embed_documents should be called once (new poll only), "
        f"got {mock_embed.embed_documents.call_count}"
    )
    # Verify the embedded text is for poll 2, not poll 1.
    embedded_texts = mock_embed.embed_documents.call_args[0][0]
    assert str(new_poll) in embedded_texts[0], (
        f"Embedded text should contain poll {new_poll}, got: {embedded_texts!r}"
    )

    # qdrant.upsert must have been called exactly once (new poll only).
    assert mock_qdrant.upsert.call_count == 1, (
        f"qdrant.upsert should be called once (new poll only), "
        f"got {mock_qdrant.upsert.call_count}"
    )

    # Only the item that did work consumes the batch budget; the present item
    # is tracked separately (batch-window stall fix).
    assert report.processed == 1, (
        f"Only the NEW item counts as processed, got {report.processed}"
    )
    assert report.present_skips == 1, (
        f"The present item must be counted as a present-skip, got {report.present_skips}"
    )

    # chunks_upserted reflects only the newly-embedded item's chunks.
    assert report.chunks_upserted == 1, (
        f"chunks_upserted must be 1 (new poll only), got {report.chunks_upserted}"
    )


# ---------------------------------------------------------------------------
# Chunk-shrink orphan cleanup — delete before upsert when chunks are missing
# ---------------------------------------------------------------------------


def test_new_item_upserts_without_delete() -> None:
    """A brand-new item (no stored footprint) must embed+upsert WITHOUT any
    delete (only orphan point ids — existing − new — are ever deleted;
    a new item has none).

    Setup: poll 1's chunk point IDs are NOT in Qdrant (scroll returns []).
    Expected:
      - qdrant.delete never called (no orphans exist).
      - qdrant.upsert called once.
      - report.chunks_upserted == 1.
    """

    poll_id = 42
    connector = StubConnector(poll_ids=[poll_id])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    # footprint scroll returns nothing → chunk missing → embed+upsert fires.
    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    mock_qdrant.delete.assert_not_called()
    assert mock_qdrant.upsert.call_count == 1, (
        f"qdrant.upsert must be called once, got {mock_qdrant.upsert.call_count}"
    )
    assert report.chunks_upserted == 1, (
        f"chunks_upserted must be 1, got {report.chunks_upserted}"
    )


def test_orphan_delete_uses_point_ids_after_embed() -> None:
    """an item with a stale extra point deletes ONLY that orphan id via
    PointIdsList — and only AFTER the embed succeeded (no loss window)."""
    poll_id = 42
    connector = StubConnector(poll_ids=[poll_id])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    source_item_id = compute_source_item_id("vote_record", str(poll_id))
    kept_pid = str(compute_chunk_id(source_item_id, 0))
    orphan_pid = str(compute_chunk_id(source_item_id, 1))  # stale higher-index chunk
    mock_qdrant.scroll.side_effect = _footprint_scroll(
        [
            SimpleNamespace(
                id=kept_pid, payload={"source_item_id": str(source_item_id)}
            ),
            SimpleNamespace(
                id=orphan_pid, payload={"source_item_id": str(source_item_id)}
            ),
        ]
    )

    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    assert mock_qdrant.delete.call_count == 1
    selector = mock_qdrant.delete.call_args.kwargs.get("points_selector")
    points = getattr(selector, "points", None)
    assert points is not None, f"delete must use PointIdsList, got {selector!r}"
    assert set(str(p) for p in points) == {orphan_pid}, (
        "only the orphan point id may be deleted"
    )
    assert mock_qdrant.upsert.call_count == 1
    assert report.chunks_upserted == 1


def test_orphan_cleanup_skipped_when_all_chunks_present() -> None:
    """delete is NOT called when all chunk point IDs already exist (all-present skip)."""
    from src.ingestion.ids import compute_source_item_id, compute_chunk_id

    poll_id = 7
    connector = StubConnector(poll_ids=[poll_id])
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    # Serve the chunk's stored point from the footprint scroll — all present.
    source_item_id = compute_source_item_id("vote_record", str(poll_id))
    point_id = str(compute_chunk_id(source_item_id, 0))
    mock_qdrant.scroll.side_effect = _footprint_scroll(
        [SimpleNamespace(id=point_id, payload={"source_item_id": str(source_item_id)})]
    )

    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    # delete must NOT have been called — all chunks already present.
    mock_qdrant.delete.assert_not_called()
    # embed and upsert must NOT have been called either.
    mock_embed.embed_documents.assert_not_called()
    mock_qdrant.upsert.assert_not_called()

    # Present-and-unchanged items no longer consume the batch budget.
    assert report.processed == 0, f"Expected 0 processed, got {report.processed}"
    assert report.present_skips == 1, (
        f"Expected 1 present-skip, got {report.present_skips}"
    )
    assert report.chunks_upserted == 0, (
        f"No chunks upserted when all present, got {report.chunks_upserted}"
    )


def test_content_hash_change_forces_reupsert() -> None:
    """When a re-ingested item's content_hash differs from the stored one, it is
    re-embedded and re-upserted so an upstream correction (e.g. a fixed vote tally)
    actually propagates."""
    from src.ingestion.ids import compute_source_item_id, compute_chunk_id

    poll_id = 7
    connector = HashStubConnector(poll_ids=[poll_id], content_hash="hash-NEW")
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    source_item_id = compute_source_item_id("vote_record", str(poll_id))
    point_id = str(compute_chunk_id(source_item_id, 0))
    # Point already exists, but with the OLD hash → content changed → must re-write.
    mock_qdrant.scroll.side_effect = _footprint_scroll(
        [
            SimpleNamespace(
                id=point_id,
                payload={
                    "source_item_id": str(source_item_id),
                    "content_hash": "hash-OLD",
                },
            )
        ]
    )

    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    mock_embed.embed_documents.assert_called_once()
    mock_qdrant.upsert.assert_called_once()
    assert report.chunks_upserted == 1


def test_content_hash_unchanged_skips_reupsert() -> None:
    """When the stored content_hash matches, the item is skipped — no re-embed, no upsert."""
    from src.ingestion.ids import compute_source_item_id, compute_chunk_id

    poll_id = 7
    connector = HashStubConnector(poll_ids=[poll_id], content_hash="hash-SAME")
    mock_qdrant = _make_mock_qdrant()
    mock_embed = _make_mock_embed()

    source_item_id = compute_source_item_id("vote_record", str(poll_id))
    point_id = str(compute_chunk_id(source_item_id, 0))
    mock_qdrant.scroll.side_effect = _footprint_scroll(
        [
            SimpleNamespace(
                id=point_id,
                payload={
                    "source_item_id": str(source_item_id),
                    "content_hash": "hash-SAME",
                },
            )
        ]
    )

    report = run_connector(connector, mock_qdrant, mock_embed, batch_size=10)

    mock_embed.embed_documents.assert_not_called()
    mock_qdrant.upsert.assert_not_called()
    assert report.processed == 0
    assert report.present_skips == 1
    assert report.chunks_upserted == 0
