# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Supersede-delete integration tests — fake Qdrant.

When op ingests an aligned+proceedings speech, the op connector's post_upsert
hook (the policy lives in the connector package, not the generic runner)
must graft the DIP twin's transcript PDF and issue a delete scoped to the
twin's source_item_id AND source == "dip". Duplication is transient.
"""

from __future__ import annotations

import types
import uuid

from src.ingestion.connectors.openparliament_tv.supersede import (
    supersede_dip_duplicates,
)


def _filter_mentions(obj: object, needles: tuple[str, ...]) -> bool:
    """Recursively stringify a filter/selector and check every needle appears."""
    blob = repr(obj)
    return all(n in blob for n in needles)


def _op_chunk(
    speech_key: str, source_item_id, text: str, chunk_index: int = 0
) -> types.SimpleNamespace:
    """A stub op ChunkRecord (supersede reads .speech_key/.source_item_id/.text/.chunk_index)."""
    return types.SimpleNamespace(
        speech_key=speech_key,
        source_item_id=source_item_id,
        text=text,
        chunk_index=chunk_index,
    )


# The proceedings text op ingested and its byte-for-byte DIP twin. Identical here
# (ratio 1.0 ≥ the 0.85 supersede threshold) so the twin is matched and deleted.
_SPEECH_TEXT = (
    "Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen! "
    "Wir stärken die Aus- und Weiterbildungsförderung in diesem Land."
)


def test_supersede_deletes_dip_duplicate() -> None:
    """op ingest deletes ONLY its text-matched DIP twin, by the twin's
    source_item_id (never by the non-unique speech_key)."""
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

    supersede_dip_duplicates(
        qdrant,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, "op-1", _SPEECH_TEXT)],
        connector=stub_connector,
    )

    assert qdrant.deletes, "op ingest must delete the matched DIP twin"
    assert any(
        _filter_mentions(d, ("dip-1", "dip")) for d in qdrant.deletes
    ), "delete must be scoped to the twin's source_item_id AND source == 'dip'"


def test_supersede_grafts_with_real_uuid_source_item_id() -> None:
    """Regression: ChunkRecord.source_item_id is a real uuid.UUID in production.

    The graft filter's MatchValue accepts only bool/int/str — a raw UUID raised a
    ValidationError AFTER the successful upsert, permanently disabling the op→DIP
    merge (the next run present-skipped the item). The supersede pass must
    stringify the op source_item_id before building the graft filter.
    """
    speech_key = "de-20-101-mareike-lotte-wulf-top20"
    pdf_url = "https://dserver.bundestag.de/btp/20/20101.pdf"
    dip_point = types.SimpleNamespace(
        payload={
            "speech_key": speech_key,
            "source_item_id": "dip-1",
            "citation_url": pdf_url,
            "text": _SPEECH_TEXT,
        }
    )
    qdrant = _MergeRecordingQdrant([dip_point])
    stub_connector = types.SimpleNamespace(source="op", source_type="parliamentary_speech")

    op_sid = uuid.uuid4()  # a REAL UUID, exactly as ChunkRecord carries it
    superseded = supersede_dip_duplicates(
        qdrant,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, op_sid, _SPEECH_TEXT)],
        connector=stub_connector,
    )

    assert superseded == 1, "UUID source_item_id must not break the merge"
    assert qdrant.batch_updates, "the graft must be issued (no ValidationError)"
    graft = qdrant.batch_updates[0]
    assert _filter_mentions(graft.get("update_operations"), (pdf_url, str(op_sid))), (
        "graft filter must carry the STRINGIFIED op source_item_id"
    )
    assert any(_filter_mentions(d, ("dip-1", "dip")) for d in qdrant.deletes)


def test_supersede_keeps_distinct_dip_speech_sharing_the_key() -> None:
    """A DISTINCT DIP speech that merely shares the non-unique speech_key
    (different text — a speaker's second turn op never aligned) must NOT be deleted."""
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

    superseded = supersede_dip_duplicates(
        qdrant,
        "wahlchat_chunks_dev",
        [_op_chunk(speech_key, "op-1", _SPEECH_TEXT)],
        connector=stub_connector,
    )
    assert superseded == 0, "no text match → nothing superseded"
    assert not qdrant.deletes, "a distinct same-key DIP speech must never be deleted"


def test_supersede_multichunk_dip_twin_joined_in_chunk_order() -> None:
    """Regression: a 2-chunk DIP twin served by scroll() in REVERSE chunk
    order must still match (texts joined by chunk_index, not scroll order) —
    "B+A" vs "A+B" would score ≈0.5 and silently miss the supersede."""
    speech_key = "de-20-101-mareike-lotte-wulf-top20"
    part_a = "Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen im Saal!"
    part_b = "Wir stärken die Aus- und Weiterbildungsförderung in diesem ganzen Land."
    pdf_url = "https://dserver.bundestag.de/btp/20/2000101.pdf"

    # Scroll serves chunk_index=1 FIRST — deliberately out of order.
    dip_points = [
        types.SimpleNamespace(
            payload={
                "speech_key": speech_key,
                "source_item_id": "dip-2c",
                "citation_url": pdf_url,
                "text": part_b,
                "chunk_index": 1,
            }
        ),
        types.SimpleNamespace(
            payload={
                "speech_key": speech_key,
                "source_item_id": "dip-2c",
                "citation_url": pdf_url,
                "text": part_a,
                "chunk_index": 0,
            }
        ),
    ]
    qdrant = _MergeRecordingQdrant(dip_points)
    stub_connector = types.SimpleNamespace(source="op", source_type="parliamentary_speech")

    # The op side carries the same speech as TWO chunks, listed out of order too.
    op_chunks = [
        _op_chunk(speech_key, "op-2c", part_b, chunk_index=1),
        _op_chunk(speech_key, "op-2c", part_a, chunk_index=0),
    ]

    superseded = supersede_dip_duplicates(
        qdrant, "wahlchat_chunks_dev", op_chunks, connector=stub_connector
    )

    assert superseded == 1, (
        "multi-chunk twin must match when joined in chunk_index order"
    )
    assert any(_filter_mentions(d, ("dip-2c", "dip")) for d in qdrant.deletes)


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

    supersede_dip_duplicates(
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


def test_op_connector_post_upsert_calls_supersede() -> None:
    """OpenParliamentTvConnector.post_upsert drives the supersede policy —
    the generic runner only calls the neutral hook."""
    from src.ingestion.connectors.openparliament_tv.connector import (
        OpenParliamentTvConnector,
    )

    conn = object.__new__(OpenParliamentTvConnector)  # bypass __init__ (no network)
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

    superseded = conn.post_upsert(
        qdrant, "wahlchat_chunks_dev", [_op_chunk(speech_key, "op-1", _SPEECH_TEXT)]
    )

    assert superseded == 1
    assert any(_filter_mentions(d, ("dip-1", "dip")) for d in qdrant.deletes)


def test_base_connector_post_upsert_is_noop() -> None:
    """Every other connector inherits the no-op hook — no Qdrant calls."""
    from src.ingestion.connector import BaseConnector

    class _Stub(BaseConnector):
        source_type = "vote_record"

        def discover(self, since):  # noqa: ANN001, ANN201
            return []

        def fetch(self, external_id):  # noqa: ANN001, ANN201
            return {}

        def normalize(self, raw):  # noqa: ANN001, ANN201
            return []

    qdrant = _MergeRecordingQdrant([])
    assert _Stub().post_upsert(qdrant, "wahlchat_chunks_dev", []) == 0
    assert not qdrant.deletes and not qdrant.batch_updates


def test_supersede_merge_end_to_end_in_memory() -> None:
    """End-to-end against a real in-memory Qdrant: with a dip + op point sharing a
    speech_key, supersede grafts the dip PDF into the op record's meta (WITHOUT
    clobbering video_uri/sentence_map) and deletes the dip point — one merged record
    survives carrying both links."""
    import pytest

    pytest.importorskip("qdrant_client")
    from qdrant_client import models

    # Import the REAL client from the submodule to bypass conftest's module-level
    # `qdrant_client.QdrantClient` MagicMock patch (same escape hatch conftest uses).
    from qdrant_client.qdrant_client import QdrantClient as RealQdrantClient

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
    supersede_dip_duplicates(
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
