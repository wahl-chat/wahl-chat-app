# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
The uploaded-manifesto connector driven through the REAL runner.

The connector deliberately owns no embed/upsert/cleanup logic of its own — it
relies on run_connector for replacement-safe rewrites, content-hash skips and
footprint reconciliation. These tests pin the three behaviours that depend on that
wiring being right, which unit tests of the connector alone cannot show:

  * a new document is embedded and upserted;
  * an unchanged document is skipped without re-embedding (re-runs are cheap);
  * a document removed from the manifest has its stored chunks DELETED, which is
    what makes the manifest the single statement of what should exist.
"""

from __future__ import annotations

import types
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from ingestion.connectors.manifesto_uploads.connector import (
    ManifestoUploadsConnector,
)
from ingestion.ids import compute_chunk_id
from ingestion.run import run_connector
from ingestion.schemas import ChunkRecord
from ingestion.setup_collection import EMBEDDING_DIM

_CTX = "landtagswahl-sachsen-anhalt-2026"
_SPD = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_CDU = f"public/{_CTX}/wahlprogramme/cdu/Wahlprogramm-CDU_2026-03-24.pdf"

_PAGES = {
    _SPD: [(1, "Sozial und gerecht. " * 40), (2, "Arbeit und Industrie. " * 40)],
    _CDU: [(1, "Sachsen-Anhalt staerker machen. " * 40)],
}


class _Qdrant:
    """Fake store serving the cursor scroll, footprint scrolls, and recording writes."""

    def __init__(self, existing: Optional[dict[str, dict]] = None) -> None:
        self.existing: dict[str, dict] = dict(existing or {})
        self.deletes: list[dict] = []
        self.upserts: list[dict] = []

    # -- reads ---------------------------------------------------------------

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        if kwargs.get("order_by") is not None:
            return ([], None)  # get_cursor: uploads carry no external_id

        wanted_payload = kwargs.get("with_payload") or []
        flt = kwargs.get("scroll_filter")
        conditions = {
            c.key: c.match
            for c in getattr(flt, "must", []) or []
            if hasattr(c, "match")
        }

        # discover()'s stored-object-path scan: source_type + source, no ids.
        if "meta.storage_object_path" in wanted_payload:
            return (
                [
                    types.SimpleNamespace(id=pid, payload=payload)
                    for pid, payload in self.existing.items()
                ],
                None,
            )

        # run_connector's parent-footprint scan: by source_item_id or parent key.
        siids: set[str] = set()
        parent_keys: set[str] = set()
        for key, match in conditions.items():
            values = getattr(match, "any", None)
            values = values if values is not None else [getattr(match, "value", None)]
            if key == "source_item_id":
                siids.update(str(v) for v in values)
            elif key == "source_parent_key":
                parent_keys.update(str(v) for v in values)
        return (
            [
                types.SimpleNamespace(id=pid, payload=payload)
                for pid, payload in self.existing.items()
                if str(payload.get("source_item_id")) in siids
                or str(payload.get("source_parent_key")) in parent_keys
            ],
            None,
        )

    def count(self, **kwargs):  # noqa: ANN003, ANN201
        """Count stored payloads, honouring the filter's must_not clause.

        The connector's AW-already-has-it guard counts NON-upload manifestos for a
        party+region+election. Everything this fake stores was written by the upload
        connector itself, so a filter excluding source="upload" must count zero —
        returning a bare len(existing) would make the guard fire against our own
        chunks and block every re-run.
        """
        flt = kwargs.get("count_filter")
        excluded = {
            (c.key, c.match.value)
            for c in (getattr(flt, "must_not", None) or [])
            if getattr(c, "match", None) is not None
        }
        matched = [
            payload
            for payload in self.existing.values()
            if not any(payload.get(key) == value for key, value in excluded)
        ]
        return types.SimpleNamespace(count=len(matched))

    # -- writes --------------------------------------------------------------

    def delete(self, **kwargs) -> None:  # noqa: ANN003
        self.deletes.append(kwargs)
        selector = kwargs.get("points_selector")
        for pid in getattr(selector, "points", []) or []:
            self.existing.pop(str(pid), None)

    def upsert(self, **kwargs) -> None:  # noqa: ANN003
        self.upserts.append(kwargs)


def _embed() -> MagicMock:
    mock = MagicMock()
    mock.embed_documents.side_effect = lambda texts: [
        [0.0] * EMBEDDING_DIM for _ in texts
    ]
    return mock


def _stored(chunks: list[ChunkRecord], parent_key: str) -> dict[str, dict]:
    """Render chunks the way a previous successful run would have left them."""
    return {
        str(compute_chunk_id(c.source_item_id, c.chunk_index)): {
            "source_item_id": str(c.source_item_id),
            "source_parent_key": parent_key,
            "content_hash": c.content_hash,
            "meta": {"storage_object_path": c.meta["storage_object_path"]},
        }
        for c in chunks
    }


@pytest.fixture()
def connector_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build a connector over a temp manifest, with PDF reads stubbed out."""

    def _make(*entries: str) -> ManifestoUploadsConnector:
        manifest = tmp_path / "dev.txt"
        manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
        connector = ManifestoUploadsConnector(manifest_path=manifest, env="dev")
        monkeypatch.setattr(
            "ingestion.connectors.manifesto_uploads.connector.load_pdf_pages",
            lambda object_path, env=None: {
                "pages": _PAGES[object_path],
                "total_pages": len(_PAGES[object_path]),
                "read_from": "test",
            },
        )
        return connector

    return _make


@pytest.fixture(autouse=True)
def _skip_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fake store has no fingerprint point; the real check is tested elsewhere."""
    monkeypatch.setattr("ingestion.run.check_fingerprint", lambda *a, **k: None)


# ===========================================================================
# New document
# ===========================================================================


def test_new_document_is_embedded_and_upserted(connector_factory) -> None:
    connector = connector_factory(_SPD)
    qdrant, embed = _Qdrant(), _embed()

    report = run_connector(connector, qdrant, embed, "c")

    assert report.processed == 1
    assert report.chunks_upserted > 0
    assert qdrant.upserts, "chunks must reach the store"
    assert embed.embed_documents.called
    # Nothing is deleted on a first ingest.
    assert qdrant.deletes == []


def test_upserted_payload_carries_the_retrieval_fields(connector_factory) -> None:
    connector = connector_factory(_SPD)
    qdrant = _Qdrant()

    run_connector(connector, qdrant, _embed(), "c")

    payloads = [p.payload for call in qdrant.upserts for p in call["points"]]
    assert payloads
    for payload in payloads:
        assert payload["party_id"] == "spd"
        assert payload["region"] == "DE-ST"
        assert payload["source"] == "upload"
        assert payload["source_type"] == "party_manifesto"
        assert payload["publish_date"] == "2026-09-06"
        assert payload["citation_url"].startswith("https://storage.googleapis.com/")
        # The runner stamps the per-parent key used for footprint reconciliation.
        assert payload["source_parent_key"] == f"party_manifesto:upload:{_SPD}"


def test_two_documents_are_both_processed(connector_factory) -> None:
    connector = connector_factory(_SPD, _CDU)
    qdrant = _Qdrant()

    report = run_connector(connector, qdrant, _embed(), "c")

    assert report.processed == 2
    parties = {p.payload["party_id"] for call in qdrant.upserts for p in call["points"]}
    assert parties == {"spd", "cdu"}


# ===========================================================================
# Unchanged document — re-runs must be cheap
# ===========================================================================


def test_unchanged_document_is_skipped_without_re_embedding(
    connector_factory,
) -> None:
    connector = connector_factory(_SPD)
    first_qdrant = _Qdrant()
    run_connector(connector, first_qdrant, _embed(), "c")
    already_stored = {
        str(p.id): {**p.payload, "source_item_id": p.payload["source_item_id"]}
        for call in first_qdrant.upserts
        for p in call["points"]
    }

    connector = connector_factory(_SPD)
    qdrant, embed = _Qdrant(already_stored), _embed()
    report = run_connector(connector, qdrant, embed, "c")

    assert report.present_skips == 1
    assert report.processed == 0
    assert report.chunks_upserted == 0
    embed.embed_documents.assert_not_called()
    assert qdrant.deletes == []


# ===========================================================================
# Retirement — deleting a manifest line removes the chunks
# ===========================================================================


def test_document_dropped_from_the_manifest_is_deleted(connector_factory) -> None:
    # Ingest both, then re-run with only one in the manifest.
    connector = connector_factory(_SPD, _CDU)
    seeded = _Qdrant()
    run_connector(connector, seeded, _embed(), "c")
    stored = {str(p.id): p.payload for call in seeded.upserts for p in call["points"]}
    cdu_point_ids = {
        pid for pid, payload in stored.items() if payload["party_id"] == "cdu"
    }
    assert cdu_point_ids

    connector = connector_factory(_SPD)  # CDU line removed
    qdrant = _Qdrant(stored)
    report = run_connector(connector, qdrant, _embed(), "c")

    # The retired document is reconciled: every one of its points is gone.
    deleted = {
        str(pid)
        for call in qdrant.deletes
        for pid in getattr(call.get("points_selector"), "points", []) or []
    }
    assert cdu_point_ids <= deleted, "removing a manifest line must retire its chunks"
    assert not any(payload["party_id"] == "cdu" for payload in qdrant.existing.values())
    # The surviving document is untouched (unchanged → cheap skip).
    assert report.present_skips == 1


def test_retirement_leaves_other_documents_alone(connector_factory) -> None:
    connector = connector_factory(_SPD, _CDU)
    seeded = _Qdrant()
    run_connector(connector, seeded, _embed(), "c")
    stored = {str(p.id): p.payload for call in seeded.upserts for p in call["points"]}
    spd_point_ids = {
        pid for pid, payload in stored.items() if payload["party_id"] == "spd"
    }

    connector = connector_factory(_SPD)
    qdrant = _Qdrant(stored)
    run_connector(connector, qdrant, _embed(), "c")

    assert spd_point_ids <= set(qdrant.existing)


def test_an_empty_work_list_retires_the_last_stored_upload(connector_factory) -> None:
    """The desired-state contract at its edge: nothing named → nothing stored.

    Retirement used to be guarded on a NON-EMPTY work-list, which left the FINAL
    document un-retirable: fetch() fell through to the deleted PDF, returned a
    skip_reason, and the runner preserved the old chunks forever.
    """
    connector = connector_factory(_SPD)
    seeded = _Qdrant()
    run_connector(connector, seeded, _embed(), "c")
    stored = {str(p.id): p.payload for call in seeded.upserts for p in call["points"]}
    assert stored, "precondition: the document is in the store"

    connector = connector_factory()  # present-but-empty manifest
    qdrant = _Qdrant(stored)
    run_connector(connector, qdrant, _embed(), "c")

    assert qdrant.existing == {}, "the last uploaded document must be retirable"


def test_an_empty_bucket_retires_the_last_stored_upload(
    connector_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same edge on the DEPLOYED backend, where the bucket is the desired state.

    A truly empty bucket is a legitimate empty work-list (a bucket with unparseable
    content is refused upstream instead), so deleting the last object must retire it.
    """
    from ingestion.connectors.manifesto_uploads import bucket_listing

    connector = connector_factory(_SPD)
    seeded = _Qdrant()
    run_connector(connector, seeded, _embed(), "c")
    stored = {str(p.id): p.payload for call in seeded.upserts for p in call["points"]}
    assert stored, "precondition: the document is in the store"

    class _EmptyBucket:
        def list_blobs(self, bucket_name: str, prefix: str = ""):  # noqa: ANN201
            return []

    monkeypatch.setenv("MANIFESTO_UPLOADS_SOURCE", "bucket")
    monkeypatch.setattr(bucket_listing, "_client", lambda env=None: _EmptyBucket())

    qdrant = _Qdrant(stored)
    run_connector(ManifestoUploadsConnector(env="dev"), qdrant, _embed(), "c")

    assert qdrant.existing == {}, "deleting the last object must retire its chunks"


def test_an_aw_publication_retires_the_uploaded_wahlprogramm(connector_factory) -> None:
    """End-to-end automatic cleanup, with the document still in the manifest.

    Previously the delete lived in the AW connector's post_upsert — a one-shot side
    effect that, if it failed, never ran again because the AW id was already complete.
    Deciding it here, per document, on every uploads run makes it idempotent, and the
    operator never has to remove chunks by hand.
    """
    connector = connector_factory(_SPD)
    seeded = _Qdrant()
    run_connector(connector, seeded, _embed(), "c")
    stored = {str(p.id): p.payload for call in seeded.upserts for p in call["points"]}
    assert stored, "precondition: the upload is in the store"

    class _AwPresent(_Qdrant):
        def count(self, **kwargs):  # noqa: ANN003, ANN201
            return types.SimpleNamespace(count=214)  # AW now carries the programme

    connector = connector_factory(_SPD)  # unchanged manifest — no operator step
    qdrant = _AwPresent(stored)
    run_connector(connector, qdrant, _embed(), "c")

    assert qdrant.existing == {}, "the AW copy must retire the uploaded duplicate"


def test_an_unavailable_overlap_check_writes_nothing_and_retries_next_run(
    connector_factory,
) -> None:
    """A transient count failure must not leave a permanent duplicate.

    Failing open wrote the upload while assuming "no AW copy"; the next healthy run
    then detected the AW copy and normalize() deliberately preserved the stored
    upload, so the duplicate could never be cleaned up.
    """

    class _BrokenCount(_Qdrant):
        def count(self, **kwargs):  # noqa: ANN003, ANN201
            raise RuntimeError("qdrant unavailable")

    connector = connector_factory(_SPD)
    broken = _BrokenCount()
    first = run_connector(connector, broken, _embed(), "c")

    assert broken.upserts == [], "nothing may be written while the AW check is unknown"
    assert first.chunks_upserted == 0
    assert first.failed_ids == (_SPD,), "the document is reported, to be retried"

    # Store healthy again: the document is re-offered and ingested exactly once.
    connector = connector_factory(_SPD)
    healthy = _Qdrant()
    second = run_connector(connector, healthy, _embed(), "c")

    assert second.processed == 1
    assert second.failed_ids == ()
    assert healthy.upserts


def test_replaced_document_rewrites_instead_of_duplicating(
    connector_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-uploading a corrected file under the same name refreshes the chunks."""
    connector = connector_factory(_SPD)
    seeded = _Qdrant()
    run_connector(connector, seeded, _embed(), "c")
    stored = {str(p.id): p.payload for call in seeded.upserts for p in call["points"]}

    # Same object path, different content — the content hash must force a rewrite.
    connector = connector_factory(_SPD)
    monkeypatch.setattr(
        "ingestion.connectors.manifesto_uploads.connector.load_pdf_pages",
        lambda object_path, env=None: {
            "pages": [(1, "Vollstaendig neuer Text. " * 40)],
            "total_pages": 1,
            "read_from": "test",
        },
    )
    qdrant, embed = _Qdrant(stored), _embed()
    report = run_connector(connector, qdrant, embed, "c")

    assert report.processed == 1
    assert embed.embed_documents.called
    # The shrunk document's now-surplus points are deleted, not left behind.
    assert qdrant.deletes
