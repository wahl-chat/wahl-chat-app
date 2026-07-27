# SPDX-FileCopyrightText: 2026 wahl.chat
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


# ---------------------------------------------------------------------------
# Vertex AI transport. The provider string stays "gemini" throughout — only the
# backend the client is built against changes, so the Qdrant embedding-space
# fingerprint is untouched and the existing corpus stays valid.
# ---------------------------------------------------------------------------


class _FakeCredentials:
    project_id = "key-derived-project"


@pytest.fixture()
def vertex_credentials(monkeypatch: pytest.MonkeyPatch):
    """Make get_vertex_credentials() return a fake key, bypassing the cache."""
    from src import google_credentials as gc

    gc.get_vertex_credentials.cache_clear()
    monkeypatch.setattr(gc, "get_vertex_credentials", lambda: _FakeCredentials())
    yield
    # monkeypatch restores the original (still-cached) function itself; clearing
    # the cache here would hit the lambda, which has no cache_clear.


def test_gemini_routes_to_vertex_when_credentials_present(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None, vertex_credentials: None
) -> None:
    """With Vertex credentials configured the client is built against Vertex:
    credentials + project + location, and NO api key."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("VERTEX_PROJECT_ID", "billing-project")
    monkeypatch.setenv("VERTEX_LOCATION", "europe-west4")

    client = emb.get_embeddings(task_type="RETRIEVAL_QUERY")

    assert isinstance(client, _FakeGemini)
    assert isinstance(client.kwargs["credentials"], _FakeCredentials)
    # Not auto-derived on the embeddings class — must be passed explicitly.
    assert client.kwargs["project"] == "billing-project"
    assert client.kwargs["location"] == "europe-west4"
    assert "google_api_key" not in client.kwargs
    # The vector space is unchanged; only transport moved.
    assert client.kwargs["model"] == EMBEDDING_MODEL
    assert client.kwargs["output_dimensionality"] == EMBEDDING_DIM
    assert client.kwargs["task_type"] == "RETRIEVAL_QUERY"


def test_project_falls_back_to_key_derived_value(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None, vertex_credentials: None
) -> None:
    """Without VERTEX_PROJECT_ID the project comes off the key itself."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)

    client = emb.get_embeddings()

    assert client.kwargs["project"] == "key-derived-project"


def test_embeddings_use_vertex_kill_switch(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None, vertex_credentials: None
) -> None:
    """EMBEDDINGS_USE_VERTEX=0 forces AI Studio even with credentials present."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("VERTEX_PROJECT_ID", "billing-project")
    monkeypatch.setenv("EMBEDDINGS_USE_VERTEX", "0")

    client = emb.get_embeddings()

    assert client.kwargs["google_api_key"] == "test-google-key"
    assert "credentials" not in client.kwargs
    # The safety pin that stops GOOGLE_GENAI_USE_VERTEXAI from hijacking it.
    assert client.kwargs["vertexai"] is False


def test_gemini_stays_on_ai_studio_without_credentials(
    monkeypatch: pytest.MonkeyPatch, patched_clients: None
) -> None:
    """No Vertex credentials (CI, local dev without a key) → unchanged path."""
    from src import google_credentials as gc

    gc.get_vertex_credentials.cache_clear()
    monkeypatch.delenv("VERTEX_SA_JSON", raising=False)
    monkeypatch.delenv("VERTEX_SA_JSON_FILE", raising=False)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")

    client = emb.get_embeddings()

    assert client.kwargs["google_api_key"] == "test-google-key"
    assert "credentials" not in client.kwargs
    gc.get_vertex_credentials.cache_clear()
