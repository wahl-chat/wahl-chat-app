# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for the embeddings provider factory (src/embeddings.py).

The concrete provider clients are patched with recording fakes so no API key,
network, or real model client is exercised — the tests assert only which client
the factory constructs and with which arguments.
"""

from __future__ import annotations

from typing import Any

import pytest

from src import embeddings as emb
from src.ingestion.setup_collection import EMBEDDING_DIM, EMBEDDING_MODEL


class _FakeOpenAI:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeGemini:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


@pytest.fixture()
def patched_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch both provider client classes at their import source."""
    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", _FakeOpenAI)
    monkeypatch.setattr(
        "langchain_google_genai.GoogleGenerativeAIEmbeddings", _FakeGemini
    )


def test_defaults_to_openai(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None
) -> None:
    """With no EMBEDDING_PROVIDER set the factory returns the OpenAI client
    built with the locked default model — the current behaviour, unchanged."""
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)

    client = emb.get_embeddings()

    assert isinstance(client, _FakeOpenAI)
    assert client.kwargs == {"model": EMBEDDING_MODEL}


def test_gemini_when_provider_is_gemini(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None
) -> None:
    """EMBEDDING_PROVIDER=gemini returns the Gemini client with the configured
    model and output_dimensionality pinned to EMBEDDING_DIM."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")

    client = emb.get_embeddings()

    assert isinstance(client, _FakeGemini)
    assert client.kwargs["model"] == EMBEDDING_MODEL
    assert client.kwargs["output_dimensionality"] == EMBEDDING_DIM
    assert client.kwargs["google_api_key"] == "test-google-key"
    # task_type defaults to None when the caller does not set it.
    assert client.kwargs["task_type"] is None


def test_gemini_task_type_forwarded(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None
) -> None:
    """task_type is forwarded to the Gemini client — the document/query asymmetry
    (RETRIEVAL_DOCUMENT for corpus chunks, RETRIEVAL_QUERY for the search query)."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "k")

    doc = emb.get_embeddings(task_type="RETRIEVAL_DOCUMENT")
    qry = emb.get_embeddings(task_type="RETRIEVAL_QUERY")

    assert doc.kwargs["task_type"] == "RETRIEVAL_DOCUMENT"
    assert qry.kwargs["task_type"] == "RETRIEVAL_QUERY"


def test_gemini_provider_is_case_insensitive_and_trimmed(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "  Gemini  ")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "alias-key")

    client = emb.get_embeddings()

    assert isinstance(client, _FakeGemini)
    # GEMINI_API_KEY is the accepted alias when GOOGLE_API_KEY is unset.
    assert client.kwargs["google_api_key"] == "alias-key"


def test_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "cohere")
    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
        emb.get_embeddings()


def test_explicit_overrides_win_over_env(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None
) -> None:
    """Explicit args take precedence over env (still defaults, decision-free)."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")

    client = emb.get_embeddings(
        provider="gemini", model="custom-model", output_dimensionality=1536
    )

    assert isinstance(client, _FakeGemini)
    assert client.kwargs["model"] == "custom-model"
    assert client.kwargs["output_dimensionality"] == 1536
