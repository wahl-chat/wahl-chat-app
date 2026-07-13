# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Supersede-delete integration test (D-04) — fake Qdrant.

When op ingests an aligned+proceedings speech, the runner (op-gated post-upsert
hook) must issue a `delete-by-filter(speech_key == X AND source == "dip")` so the
transient DIP duplicate is removed. Duplication is transient.

Wave-0 SCAFFOLD: the supersede hook does not exist yet. This file collects
cleanly and CAPABILITY-SKIPS until the hook lands (Wave 11-04), then runs the
real assertion against a fake Qdrant that records `delete(...)` calls.
"""

from __future__ import annotations

import types

import pytest


def _supersede_capability() -> bool:
    """True once the runner exposes an op-gated supersede-delete hook."""
    try:
        from src.ingestion import run as run_mod
    except ImportError:
        return False
    return any(
        hasattr(run_mod, name)
        for name in ("supersede_dip_duplicates", "_supersede_dip", "run_connector_with_supersede")
    )


def _filter_mentions(obj: object, needles: tuple[str, ...]) -> bool:
    """Recursively stringify a filter/selector and check every needle appears."""
    blob = repr(obj)
    return all(n in blob for n in needles)


def _op_chunk(speech_key: str, source_item_id: str, text: str) -> types.SimpleNamespace:
    """A stub op ChunkRecord (supersede reads .speech_key/.source_item_id/.text)."""
    return types.SimpleNamespace(
        speech_key=speech_key, source_item_id=source_item_id, text=text
    )


# The proceedings text op ingested and its byte-for-byte DIP twin. Identical here
# (ratio 1.0 ≥ the 0.85 supersede threshold) so the twin is matched and deleted.
_SPEECH_TEXT = (
    "Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen! "
    "Wir stärken die Aus- und Weiterbildungsförderung in diesem Land."
)


def test_supersede_deletes_dip_duplicate() -> None:
    """D-04: op ingest deletes ONLY its text-matched DIP twin, by the twin's
    source_item_id (never by the non-unique speech_key)."""
    if not _supersede_capability():
        pytest.skip("supersede-delete hook not yet implemented (11-04) — Wave-0 scaffold")

    from src.ingestion import run as run_mod

    speech_key = "de-20-101-mareike-lotte-wulf-top20"
    dip_point = types.SimpleNamespace(
        payload={
            "speech_key": speech_key,
            "source_item_id": "dip-1",
            "citation_url": "https://dserver.bundestag.de/btp/20/20101.pdf",
            "text": _SPEECH_TEXT,
        }
    )
    qdrant = _MergeRecordingQdrant([dip_point])
    stub_connector = types.SimpleNamespace(source="op", source_type="parliamentary_speech")

    supersede = getattr(run_mod, "supersede_dip_duplicates", None)
    assert supersede is not None
    supersede(
        qdrant,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, "op-1", _SPEECH_TEXT)],
        connector=stub_connector,
    )

    assert qdrant.deletes, "op ingest must delete the matched DIP twin"
    assert any(
        _filter_mentions(d, ("dip-1", "dip")) for d in qdrant.deletes
    ), "delete must be scoped to the twin's source_item_id AND source == 'dip'"


def test_supersede_keeps_distinct_dip_speech_sharing_the_key() -> None:
    """HIGH-1: a DISTINCT DIP speech that merely shares the non-unique speech_key
    (different text — a speaker's second turn op never aligned) must NOT be deleted."""
    if not _supersede_capability():
        pytest.skip("supersede hook not yet implemented")

    from src.ingestion import run as run_mod

    speech_key = "de-20-101-mareike-lotte-wulf-top20"
    # DIP row under the same key but a completely different speech → must survive.
    other = types.SimpleNamespace(
        payload={
            "speech_key": speech_key,
            "source_item_id": "dip-other",
            "citation_url": "https://dserver.bundestag.de/btp/20/20101.pdf",
            "text": "Zur Geschäftsordnung: ich beantrage eine namentliche Abstimmung.",
        }
    )
    qdrant = _MergeRecordingQdrant([other])
    stub_connector = types.SimpleNamespace(source="op", source_type="parliamentary_speech")

    superseded = run_mod.supersede_dip_duplicates(
        qdrant,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, "op-1", _SPEECH_TEXT)],
        connector=stub_connector,
    )
    assert superseded == 0, "no text match → nothing superseded"
    assert not qdrant.deletes, "a distinct same-key DIP speech must never be deleted"


class _MergeRecordingQdrant:
    """Fake QdrantClient that serves DIP points from scroll() and records the
    batch graft + delete calls."""

    def __init__(self, dip_points: list) -> None:
        self._dip_points = dip_points
        self._scrolled = False
        self.batch_updates: list[dict] = []
        self.deletes: list[dict] = []

    def scroll(self, *a, **k):  # noqa: ANN002, ANN003, ANN201
        # First page returns the DIP duplicates, then exhausted (offset=None).
        if not self._scrolled:
            self._scrolled = True
            return (self._dip_points, None)
        return ([], None)

    def batch_update_points(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        self.batch_updates.append(k)

    def upsert(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        pass

    def delete(self, *a, **k) -> None:  # noqa: ANN002, ANN003
        self.deletes.append({"args": a, "kwargs": k})


def test_supersede_grafts_dip_pdf_onto_op_before_delete() -> None:
    """Merge (not replace): op ingest harvests the DIP duplicate's transcript PDF and
    grafts it onto the op record (meta.transcript_pdf_url) in a durable batch BEFORE
    deleting the DIP point, so one speech source keeps both the video and the PDF."""
    if not _supersede_capability():
        pytest.skip("supersede-delete hook not yet implemented (11-04) — Wave-0 scaffold")

    from src.ingestion import run as run_mod

    speech_key = "de-20-101-mareike-lotte-wulf-top20"
    pdf_url = "https://dserver.bundestag.de/btp/20/2000101.pdf"
    dip_point = types.SimpleNamespace(
        payload={
            "speech_key": speech_key,
            "source_item_id": "dip-1",
            "citation_url": pdf_url,
            "text": _SPEECH_TEXT,
        }
    )
    qdrant = _MergeRecordingQdrant([dip_point])
    stub_connector = types.SimpleNamespace(
        source="op",
        source_type="parliamentary_speech",
    )

    run_mod.supersede_dip_duplicates(
        qdrant,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, "op-1", _SPEECH_TEXT)],
        connector=stub_connector,
    )

    # Grafted the harvested PDF onto THIS op record (by its source_item_id) under
    # meta, durably (wait=True).
    assert qdrant.batch_updates, "must graft the DIP transcript PDF onto the op record"
    graft = qdrant.batch_updates[0]
    assert graft.get("wait") is True, "graft must be durable before the destructive delete"
    assert _filter_mentions(graft.get("update_operations"), (pdf_url, "op-1", "op")), (
        "graft must set transcript_pdf_url on the op source_item_id AND source == 'op'"
    )
    # And still deletes the now-redundant DIP twin (by its source_item_id).
    assert qdrant.deletes
    assert any(_filter_mentions(d, ("dip-1", "dip")) for d in qdrant.deletes)


def test_supersede_merge_end_to_end_in_memory() -> None:
    """End-to-end against a real in-memory Qdrant: with a dip + op point sharing a
    speech_key, supersede grafts the dip PDF into the op record's meta (WITHOUT
    clobbering video_uri/sentence_map) and deletes the dip point — one merged record
    survives carrying both links."""
    if not _supersede_capability():
        pytest.skip("supersede-delete hook not yet implemented (11-04) — Wave-0 scaffold")

    pytest.importorskip("qdrant_client")
    from qdrant_client import models

    # Import the REAL client from the submodule to bypass conftest's module-level
    # `qdrant_client.QdrantClient` MagicMock patch (same escape hatch conftest uses).
    from qdrant_client.qdrant_client import QdrantClient as RealQdrantClient

    from src.ingestion import run as run_mod

    client = RealQdrantClient(":memory:")
    client.create_collection(
        "wahlchat_chunks_dev",
        vectors_config={"dense": models.VectorParams(size=3, distance=models.Distance.COSINE)},
    )
    speech_key = "de-20-101-mareike-lotte-wulf-top20"
    pdf_url = "https://dserver.bundestag.de/btp/20/2000101.pdf"
    client.upsert(
        "wahlchat_chunks_dev",
        points=[
            models.PointStruct(
                id=1,
                vector={"dense": [0.1, 0.2, 0.3]},
                payload={
                    "speech_key": speech_key,
                    "source": "dip",
                    "source_item_id": "dip-1",
                    "citation_url": pdf_url,
                    "text": _SPEECH_TEXT,
                },
            ),
            models.PointStruct(
                id=2,
                vector={"dense": [0.1, 0.2, 0.3]},
                payload={
                    "speech_key": speech_key,
                    "source": "op",
                    "source_item_id": "op-2",
                    "text": _SPEECH_TEXT,
                    "citation_url": "https://cdn.example/clip.mp4#t=87.5",
                    "meta": {
                        "video_uri": "https://cdn.example/clip.mp4",
                        "sentence_map": [{"text": "a", "ts_start": 87.5}],
                    },
                },
            ),
        ],
    )

    stub_connector = types.SimpleNamespace(source="op", source_type="parliamentary_speech")
    run_mod.supersede_dip_duplicates(
        client,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, "op-2", _SPEECH_TEXT)],
        connector=stub_connector,
    )

    # The op point (id=2) survives with BOTH links; video meta is intact.
    op_point = client.retrieve("wahlchat_chunks_dev", ids=[2], with_payload=True)[0]
    op_meta = op_point.payload["meta"]
    assert op_meta["transcript_pdf_url"] == pdf_url, "DIP PDF must be grafted onto op"
    assert op_meta["video_uri"] == "https://cdn.example/clip.mp4", "video_uri must survive the graft"
    assert op_meta["sentence_map"], "sentence_map must survive the graft"

    # The dip duplicate (id=1) is deleted → one merged record remains.
    assert client.retrieve("wahlchat_chunks_dev", ids=[1], with_payload=True) == []
