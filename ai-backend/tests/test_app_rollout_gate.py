# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Rollout gate: the app must refuse to boot on an unpopulated corpus ONLY when
REQUIRE_CORPUS is explicitly set — otherwise local dev / CI boot on empty."""

import pytest

from src import app as app_module
from wahlchat_common import corpus as setup_collection


class _FakeCount:
    def __init__(self, count: int) -> None:
        self.count = count


class _FakeClient:
    def __init__(self, *, exists: bool, count: int = 0) -> None:
        self._exists = exists
        self._count = count

    def collection_exists(self, _name: str) -> bool:
        return self._exists

    def count(
        self,
        collection_name: str,
        count_filter: object = None,
        exact: bool = True,
    ) -> _FakeCount:
        # count_filter excludes the fingerprint sentinel in production; the
        # fake's configured count already represents the corpus-only total.
        return _FakeCount(self._count)


def test_gate_disabled_is_noop_even_with_no_qdrant(monkeypatch):
    """Unset REQUIRE_CORPUS → no client is ever built, no raise (local/CI path)."""
    monkeypatch.delenv("REQUIRE_CORPUS", raising=False)

    def _boom() -> None:  # pragma: no cover - must never be called
        raise AssertionError("corpus_point_count must not run when gate is disabled")

    monkeypatch.setattr(setup_collection, "corpus_point_count", _boom)
    app_module.enforce_corpus_rollout_gate()  # no exception


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes"])
def test_gate_enabled_raises_on_missing_collection(monkeypatch, truthy):
    monkeypatch.setenv("REQUIRE_CORPUS", truthy)
    monkeypatch.setattr(setup_collection, "corpus_point_count", lambda: None)
    with pytest.raises(RuntimeError, match="missing"):
        app_module.enforce_corpus_rollout_gate()


def test_gate_enabled_raises_on_empty_collection(monkeypatch):
    monkeypatch.setenv("REQUIRE_CORPUS", "true")
    monkeypatch.setattr(setup_collection, "corpus_point_count", lambda: 0)
    with pytest.raises(RuntimeError, match="empty"):
        app_module.enforce_corpus_rollout_gate()


def test_gate_enabled_passes_on_populated_collection(monkeypatch):
    monkeypatch.setenv("REQUIRE_CORPUS", "true")
    monkeypatch.setattr(setup_collection, "corpus_point_count", lambda: 42)
    app_module.enforce_corpus_rollout_gate()  # no exception


def test_corpus_point_count_missing_vs_empty_vs_populated():
    assert setup_collection.corpus_point_count(_FakeClient(exists=False)) is None
    assert setup_collection.corpus_point_count(_FakeClient(exists=True, count=0)) == 0
    assert setup_collection.corpus_point_count(_FakeClient(exists=True, count=7)) == 7
