# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Event-scoped single-document runs (the Firebase storage-trigger entrypoints).

``single.py`` deliberately adds nothing but a one-path discover() on top of the
connector + runner, so these tests pin exactly that seam: the event's document
— and ONLY it — is ingested or retired, with the runner's usual guarantees
(hash skip, footprint delete, floor semantics) intact. The store/embedding
fakes are shared with test_runner_integration, which covers the mechanics.
"""

from __future__ import annotations

import pytest

from ingestion.connectors.manifesto_uploads.mappers.corpus import (
    build_upload_manifesto_records,
)
from ingestion.connectors.manifesto_uploads.single import ingest_one, retire_one
from ingestion.connectors.manifesto_uploads.storage_paths import parse_object_path
from ingestion.connectors.manifesto_uploads.election_fixtures import load_election
from ingestion.ids import compute_chunk_id
from tests.connectors.manifesto_uploads.test_runner_integration import (
    _CDU,
    _PAGES,
    _SPD,
    _Qdrant,
    _embed,
)


def _seeded(chunks, parent_key: str) -> dict[str, dict]:
    """Render chunks the way a previous successful run left them — FULL payloads,
    so the fakes' filter-sensitive fields (source, party_id) are present and the
    AW-overlap guard's must_not(source="upload") excludes our own chunks."""
    return {
        str(compute_chunk_id(c.source_item_id, c.chunk_index)): {
            **c.model_dump(mode="json", exclude_none=True),
            "source_parent_key": parent_key,
        }
        for c in chunks
    }


@pytest.fixture(autouse=True)
def _stub_io(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setattr(
        "ingestion.connectors.manifesto_uploads.connector.load_pdf_pages",
        lambda object_path, env=None: {
            "pages": _PAGES[object_path],
            "total_pages": len(_PAGES[object_path]),
            "read_from": "test",
        },
    )
    monkeypatch.setattr("ingestion.run.check_fingerprint", lambda *a, **k: None)


def _spd_chunks():
    ref = parse_object_path(_SPD)
    fixture = load_election(ref.context_id, "dev")
    from ingestion.chunking import chunk_pages

    return build_upload_manifesto_records(
        ref=ref,
        fixture=fixture,
        chunks=list(chunk_pages(_PAGES[_SPD])),
        citation_url=ref.citation_url("dev"),
        total_pages=len(_PAGES[_SPD]),
    )


def test_ingest_one_processes_exactly_the_event_document() -> None:
    qdrant, embed = _Qdrant(), _embed()

    report = ingest_one(_SPD, env="dev", qdrant=qdrant, embed=embed)

    assert report.processed == 1
    assert report.failed_ids == ()
    payloads = [p.payload for call in qdrant.upserts for p in call["points"]]
    assert payloads
    assert {p["meta"]["storage_object_path"] for p in payloads} == {_SPD}
    assert all(
        p["source_parent_key"] == f"party_manifesto:upload:{_SPD}" for p in payloads
    )


def test_ingest_one_is_a_cheap_skip_when_unchanged() -> None:
    chunks = _spd_chunks()
    qdrant = _Qdrant(existing=_seeded(chunks, f"party_manifesto:upload:{_SPD}"))
    embed = _embed()

    report = ingest_one(_SPD, env="dev", qdrant=qdrant, embed=embed)

    assert report.processed == 0
    assert report.present_skips == 1
    assert not embed.embed_documents.called
    assert qdrant.upserts == []


def test_ingest_one_never_touches_other_documents() -> None:
    # A stored CDU document must survive an SPD event untouched — the whole
    # point of the event-scoped discover() versus a full reconcile.
    ref = parse_object_path(_CDU)
    fixture = load_election(ref.context_id, "dev")
    from ingestion.chunking import chunk_pages

    cdu_chunks = build_upload_manifesto_records(
        ref=ref,
        fixture=fixture,
        chunks=list(chunk_pages(_PAGES[_CDU])),
        citation_url=ref.citation_url("dev"),
        total_pages=len(_PAGES[_CDU]),
    )
    qdrant = _Qdrant(existing=_seeded(cdu_chunks, f"party_manifesto:upload:{_CDU}"))

    report = ingest_one(_SPD, env="dev", qdrant=qdrant, embed=_embed())

    assert report.processed == 1, "the SPD event must still ingest"
    upserted = [p.payload for call in qdrant.upserts for p in call["points"]]
    assert {p["meta"]["storage_object_path"] for p in upserted} == {_SPD}
    assert qdrant.deletes == []
    assert any(qdrant.existing), "the CDU footprint must remain stored"


def test_retire_one_deletes_the_full_footprint() -> None:
    chunks = _spd_chunks()
    qdrant = _Qdrant(existing=_seeded(chunks, f"party_manifesto:upload:{_SPD}"))
    embed = _embed()

    report = retire_one(_SPD, env="dev", qdrant=qdrant, embed=embed)

    assert report.processed == 1
    assert qdrant.existing == {}
    assert not embed.embed_documents.called


def test_retire_one_on_unknown_document_is_a_noop() -> None:
    qdrant = _Qdrant()

    report = retire_one(_SPD, env="dev", qdrant=qdrant, embed=_embed())

    assert report.processed == 0
    assert qdrant.deletes == []


def test_below_floor_event_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Floor after the election date → the document is out of scope: neither
    # ingested nor retired, exactly like the reconcile run's semantics.
    monkeypatch.setenv("MANIFESTO_UPLOADS_SINCE", "2030-01-01")
    chunks = _spd_chunks()
    qdrant = _Qdrant(existing=_seeded(chunks, f"party_manifesto:upload:{_SPD}"))

    report = ingest_one(_SPD, env="dev", qdrant=qdrant, embed=_embed())
    assert report.processed == 0
    assert qdrant.upserts == []

    report = retire_one(_SPD, env="dev", qdrant=qdrant, embed=_embed())
    assert report.processed == 0
    assert qdrant.deletes == []
    assert any(qdrant.existing), "an out-of-scope document must never be deleted"
