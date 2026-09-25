"""Offline tests for the local corpus snapshots in ``src.data_analysis.corpus``.

Qdrant is replaced by an in-memory fake that honours the same scroll/count
surface the module uses, so the whole fetch → validate → save → load path runs
without network access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

# pandas and pyarrow live in the opt-in `analysis` dependency group, which the
# default sync (and so the regular backend suite) does not install. Without this
# guard the missing import would abort collection of the whole test run.
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from src.data_analysis import corpus  # noqa: E402

DIM = 4
COLLECTION = "wahlchat_chunks_test"
FINGERPRINT = {
    "source_type": corpus.FINGERPRINT_SOURCE_TYPE,
    "embedding_provider": "gemini",
    "embedding_model": "gemini-embedding-2",
    "embedding_dim": DIM,
}


@dataclass
class FakePoint:
    id: Any
    vector: dict | None
    payload: dict | None


class FakeQdrant:
    """Offset-paginated scroll over a fixed point list; the filter is ignored
    because the tests never place the fingerprint sentinel in ``points``."""

    def __init__(self, points: list[FakePoint]):
        self.points = points

    def collection_exists(self, name: str) -> bool:
        return name == COLLECTION

    def scroll(self, collection_name, offset=None, limit=10, scroll_filter=None,
               with_vectors=False, with_payload=True):
        start = offset or 0
        page = self.points[start:start + limit]
        out = [
            FakePoint(p.id, p.vector if with_vectors else None, p.payload)
            for p in page
        ]
        nxt = start + limit
        return out, (nxt if nxt < len(self.points) else None)

    def count(self, collection_name, count_filter=None, exact=True):
        return SimpleNamespace(count=len(self.points))


def _points(n: int = 7) -> list[FakePoint]:
    rng = np.random.default_rng(0)
    pts = []
    for i in range(n):
        payload: dict[str, Any] = {"text": f"chunk {i}", "region": "DE"}
        if i % 3:  # content_hash is Optional in the ingestion contract
            payload["content_hash"] = f"h{i}"
        if i == 0:  # heterogeneous payloads: one source type carries an extra key
            payload["vote_id"] = 42
        pts.append(FakePoint(uuid.uuid5(uuid.NAMESPACE_URL, str(i)),
                             {"dense": rng.random(DIM).tolist()}, payload))
    return pts


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    client = FakeQdrant(_points())
    monkeypatch.setattr(corpus, "QdrantClient", lambda **_: client)
    monkeypatch.setattr(corpus, "read_fingerprint", lambda *_: FINGERPRINT)
    monkeypatch.setattr(corpus, "qdrant_root", lambda *_, **__: tmp_path)
    return client, tmp_path


def test_datetime_is_fixed_width_and_sorts_chronologically():
    early = corpus.Datetime(2026, 3, 3, 9, 5, 1)
    late = corpus.Datetime(2026, 3, 13, 9, 5, 1)
    assert len(str(early)) == len(str(late)) == 15
    assert str(early) < str(late)


def test_snapshot_hash_ignores_order_but_not_columns():
    pairs = [("b", "x"), ("a", None)]
    base = corpus.snapshot_hash(pairs, ["text", "region"])
    assert base == corpus.snapshot_hash(reversed(pairs), ["region", "text"])
    assert base != corpus.snapshot_hash(pairs, ["text", "region", "vote_id"])
    # column names are delimited, so a different split of the same letters differs
    assert corpus.snapshot_hash(pairs, ["ab", "c"]) != corpus.snapshot_hash(pairs, ["a", "bc"])


def test_local_hash_matches_remote_hash(fake_env):
    client, _ = fake_env
    path = corpus._fetch_export(collection=COLLECTION, scroll_limit=3)
    local = corpus.load_corpus(path).manifest.snapshot_hash
    assert local == corpus.remote_snapshot_hash(client, COLLECTION)
    manifest = corpus.load_corpus(path).manifest
    assert corpus.is_stale(client, COLLECTION, manifest, level="exact") is False


def test_round_trip_and_load_last_export(fake_env):
    client, root = fake_env
    path = corpus._fetch_export(collection=COLLECTION, scroll_limit=3)
    # an interrupted later download must not be mistaken for the newest version
    (root / COLLECTION / "29990101T000000_ffff.partial").mkdir()

    loaded = corpus.load_last_export(COLLECTION)
    assert loaded.path == path
    assert isinstance(loaded.vectors, np.memmap)
    assert loaded.vectors.shape == (len(client.points), DIM)
    assert list(loaded.ids) == [str(p.id) for p in client.points]
    assert loaded.manifest.payload_columns == sorted(["text", "region", "content_hash", "vote_id"])
    assert loaded.manifest.n_rows == loaded.manifest.point_count


def test_duplicate_points_are_rejected_before_saving(fake_env):
    client, root = fake_env
    client.points.append(client.points[0])
    client.count = lambda *_, **__: SimpleNamespace(count=len(client.points))
    with pytest.raises(corpus.FetchingError, match="duplicated point ids"):
        corpus._fetch_export(collection=COLLECTION)
    assert not any((root / COLLECTION).glob("*/" + corpus.MANIFEST))


def test_truncated_scroll_is_rejected(fake_env):
    client, _ = fake_env
    client.count = lambda *_, **__: SimpleNamespace(count=len(client.points) + 1)
    with pytest.raises(corpus.FetchingError, match="incomplete export"):
        corpus._fetch_export(collection=COLLECTION)


def test_misaligned_corpus_fails_at_construction(fake_env):
    path = corpus._fetch_export(collection=COLLECTION)
    good = corpus.load_corpus(path)
    with pytest.raises(ValueError):
        corpus.Corpus(meta=good.meta.iloc[:2], vectors=good.vectors, ids=good.ids,
                      manifest=good.manifest, path=path)


def _no_staging_left(root: Path) -> bool:
    return not any((root / COLLECTION).glob(".*.partial"))


def test_collection_growing_mid_scroll_is_rejected(fake_env):
    # the file is sized on the first count: a collection that grows while the
    # scroll runs would overflow it, which must fail instead of being truncated
    client, root = fake_env
    counts = iter([len(client.points) - 2, len(client.points)])
    client.count = lambda *_, **__: SimpleNamespace(count=next(counts))
    with pytest.raises(corpus.FetchingError, match="grew during the fetching"):
        corpus._fetch_export(collection=COLLECTION, scroll_limit=3)
    assert _no_staging_left(root)


def test_failed_validation_removes_the_staging_folder(fake_env):
    client, root = fake_env
    client.points.append(client.points[0])
    client.count = lambda *_, **__: SimpleNamespace(count=len(client.points))
    with pytest.raises(corpus.FetchingError, match="duplicated point ids"):
        corpus._fetch_export(collection=COLLECTION)
    assert _no_staging_left(root)
    assert not any((root / COLLECTION).glob("*/" + corpus.MANIFEST))


def test_non_finite_vectors_are_rejected(fake_env):
    client, root = fake_env
    client.points[3].vector["dense"][1] = float("nan")
    with pytest.raises(corpus.FetchingError, match="non-finite"):
        corpus._fetch_export(collection=COLLECTION)
    assert _no_staging_left(root)


def test_snapshot_vectors_match_the_scrolled_points(fake_env):
    # rows written page by page into the memory map must land in scroll order
    client, _ = fake_env
    path = corpus._fetch_export(collection=COLLECTION, scroll_limit=3)
    expected = np.asarray([p.vector["dense"] for p in client.points], dtype=np.float32)
    np.testing.assert_array_equal(corpus.load_corpus(path).vectors, expected)


def test_project_root_is_the_repository_not_git_internals(monkeypatch, tmp_path):
    # started from outside the repository, as a notebook opened elsewhere would be
    monkeypatch.chdir(tmp_path)
    root = corpus.project_root()
    assert root.name not in {".git", ".bare"}
    assert Path(corpus.__file__).resolve().is_relative_to(root)


def test_vector_of_the_wrong_dimension_is_rejected(fake_env):
    # a length-1 vector would broadcast across the whole preallocated row
    client, root = fake_env
    client.points[4].vector["dense"] = [0.5]
    with pytest.raises(corpus.FetchingError, match="4-dimensional"):
        corpus._fetch_export(collection=COLLECTION, scroll_limit=3)
    assert _no_staging_left(root)


def _unreachable(cause: Exception):
    def fail(*_, **__):
        raise ResponseHandlingException(cause)
    return fail


@pytest.mark.parametrize("level", ["count", "exact"])
@pytest.mark.parametrize(
    "cause",
    [httpx.ConnectError("nodename nor servname provided"), httpx.ConnectTimeout("timed out")],
    ids=["connect-error", "connect-timeout"],
)
def test_unreachable_server_makes_the_check_answer_none(fake_env, cause, level):
    # offline, the freshness check must warn and answer "cannot tell", not raise
    client, _ = fake_env
    manifest = corpus.load_corpus(corpus._fetch_export(collection=COLLECTION)).manifest
    client.count = client.scroll = _unreachable(cause)
    with pytest.warns(UserWarning, match="Unable to connect"):
        assert corpus.is_stale(client, COLLECTION, manifest, level=level) is None


@pytest.mark.parametrize(
    "cause",
    [
        ValueError("malformed response"),
        httpx.LocalProtocolError("invalid request"),
        httpx.UnsupportedProtocol("no scheme"),
    ],
    ids=["validation", "local-protocol", "unsupported-protocol"],
)
def test_non_network_failure_of_the_check_still_raises(fake_env, cause):
    # the same wrapper also carries unparsable responses, client-side bugs and a
    # malformed QDRANT_URL: none of them means being offline
    client, _ = fake_env
    manifest = corpus.load_corpus(corpus._fetch_export(collection=COLLECTION)).manifest
    client.count = _unreachable(cause)
    with pytest.raises(ResponseHandlingException):
        corpus.is_stale(client, COLLECTION, manifest)
