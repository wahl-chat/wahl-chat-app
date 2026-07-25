# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Config-resolution tests for setup_collection.

The collection name, embedding model and embedding dimension are read from env
at import time so a second vector space (e.g. a parallel Gemini collection) can
be created alongside the existing one without editing code. With no env set the
defaults must remain the locked OpenAI text-embedding-3-large @ 3072 space.

These tests reload the module under a patched environment and restore it in a
finally block so no other test observes the overridden values.
"""

from __future__ import annotations

import importlib

import pytest

import src.ingestion.setup_collection as sc


def test_defaults_unchanged_with_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """With none of the override vars set, defaults are the locked values."""
    monkeypatch.delenv("COLLECTION_NAME", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_DIM", raising=False)
    monkeypatch.setenv("ENV", "dev")
    reloaded = importlib.reload(sc)
    try:
        assert reloaded.COLLECTION_NAME == "wahlchat_chunks_dev"
        assert reloaded.EMBEDDING_MODEL == "text-embedding-3-large"
        assert reloaded.EMBEDDING_DIM == 3072
    finally:
        monkeypatch.undo()
        importlib.reload(sc)


def test_name_model_and_dim_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A parallel Gemini collection can be defined entirely via env."""
    monkeypatch.setenv("COLLECTION_NAME", "wahlchat_chunks_gemini_dev")
    monkeypatch.setenv("EMBEDDING_MODEL", "gemini-embedding-001")
    monkeypatch.setenv("EMBEDDING_DIM", "3072")
    reloaded = importlib.reload(sc)
    try:
        assert reloaded.COLLECTION_NAME == "wahlchat_chunks_gemini_dev"
        assert reloaded.EMBEDDING_MODEL == "gemini-embedding-001"
        assert reloaded.EMBEDDING_DIM == 3072
        # The index spec set is unaffected by the vector-space config.
        assert reloaded._REQUIRED_INDEXES == sc._REQUIRED_INDEXES
    finally:
        monkeypatch.undo()
        importlib.reload(sc)


def test_collection_name_env_overrides_env_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit COLLECTION_NAME wins over the ENV-derived default name."""
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("COLLECTION_NAME", "custom_collection")
    reloaded = importlib.reload(sc)
    try:
        assert reloaded.COLLECTION_NAME == "custom_collection"
    finally:
        monkeypatch.undo()
        importlib.reload(sc)
