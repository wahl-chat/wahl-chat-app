# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for collection name, model, and dimension.

Those values are read from the environment at import time.
With no variables set, the defaults are gemini-embedding-2 and 3072 dimensions.
The constants live in ``wahlchat_common.corpus``.
``setup_collection`` re-exports them.
These tests reload both modules.
A reload of ``setup_collection`` alone keeps the cached corpus values.
Each test restores the modules in a ``finally`` block.
"""

from __future__ import annotations

import importlib

import pytest

import wahlchat_common.corpus as corpus
import ingestion.setup_collection as sc


def test_defaults_unchanged_with_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """With none of the override vars set, defaults are the locked values."""
    monkeypatch.delenv("COLLECTION_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_DIM", raising=False)
    monkeypatch.setenv("ENV", "dev")
    importlib.reload(corpus)
    reloaded = importlib.reload(sc)
    try:
        assert reloaded.COLLECTION_NAME == "wahlchat_chunks_dev"
        assert reloaded.EMBEDDING_MODEL == "gemini-embedding-2"
        assert reloaded.EMBEDDING_DIM == 3072
    finally:
        monkeypatch.undo()
        importlib.reload(corpus)
        importlib.reload(sc)


def test_name_model_and_dim_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables set the collection name, model, and dimension."""
    monkeypatch.setenv("COLLECTION_NAME", "wahlchat_chunks_gemini_dev")
    monkeypatch.setenv("EMBEDDING_MODEL", "gemini-embedding-001")
    monkeypatch.setenv("EMBEDDING_DIM", "3072")
    importlib.reload(corpus)
    reloaded = importlib.reload(sc)
    try:
        assert reloaded.COLLECTION_NAME == "wahlchat_chunks_gemini_dev"
        assert reloaded.EMBEDDING_MODEL == "gemini-embedding-001"
        assert reloaded.EMBEDDING_DIM == 3072
        # The index spec set is unaffected by the vector-space config.
        assert reloaded._REQUIRED_INDEXES == sc._REQUIRED_INDEXES
    finally:
        monkeypatch.undo()
        importlib.reload(corpus)
        importlib.reload(sc)


def test_collection_name_env_overrides_env_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit COLLECTION_NAME wins over the ENV-derived default name."""
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("COLLECTION_NAME", "custom_collection")
    importlib.reload(corpus)
    reloaded = importlib.reload(sc)
    try:
        assert reloaded.COLLECTION_NAME == "custom_collection"
    finally:
        monkeypatch.undo()
        importlib.reload(corpus)
        importlib.reload(sc)
