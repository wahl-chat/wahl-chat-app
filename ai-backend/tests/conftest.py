# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared pytest fixtures for the ai-backend test suite.

The patch_chat_io fixture patches all
external I/O calls in the chat stream so the smoke test requires no live API
keys, no Qdrant service, and no Firestore data.

Primary patches:
  1. src.chat_service.identify_relevant_docs_with_llm_based_reranking
       Replaces the Qdrant similarity search (embed.aembed_query +
       qdrant_client.search) with a deterministic list of Documents.

  2. src.chatbot_async.stream_answer_from_llms
       Replaces the LLM token stream (llm.model.astream) with a deterministic
       async generator yielding two AIMessageChunk objects.

Additional Firestore and LLM helper calls made by generate_chat_stream are
also patched here because they are all "external I/O" in the same sense.
The SSE generator, FastAPI route, EventSourceResponse framing, and
data-stream protocol (f/0/8/e/d/[DONE]) all run live.

IMPORTANT: The src.* modules instantiate clients at module level (ChatOpenAI,
ChatGoogleGenerativeAI, firebase_admin, etc.). These require that certain env
vars be set before import — see the os.environ.setdefault() calls at the top of
this file which supply safe dummy values for CI.

The test uses httpx.AsyncASGITransport(app=app) to run in-process, which
is the only reliable way to apply monkeypatching to a FastAPI SSE endpoint
without a separately-running server.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Set required env vars before any src.* imports happen.
# These are safe dummy values — no real credentials are used.
# The conftest patches all external I/O before it can be exercised.
# ---------------------------------------------------------------------------
os.environ.setdefault("API_NAME", "wahl-chat-api")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "localhost:8081")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "dummy-openai-key-for-ci")
os.environ.setdefault("GOOGLE_API_KEY", "dummy-google-key-for-ci")

# ---------------------------------------------------------------------------
# Patch QdrantClient BEFORE src.vector_store_helper is imported.
# vector_store_helper.py creates QdrantVectorStore instances at module level;
# the QdrantVectorStore constructor calls qdrant_client.get_collection() which
# makes an HTTP request.  We replace the entire QdrantClient class so module-
# level instantiation produces a MagicMock that never touches the network.
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock, AsyncMock, patch as _patch

_qdrant_client_mock = MagicMock()
_qdrant_client_mock.get_collections.return_value = MagicMock(collections=[])
_qdrant_client_mock.search.return_value = []

_qdrant_patch = _patch("qdrant_client.QdrantClient", return_value=_qdrant_client_mock)
_qdrant_patch.start()

# Also patch QdrantVectorStore to avoid any further network calls at init time.
_vector_store_mock = MagicMock()
_qvs_patch = _patch(
    "langchain_qdrant.QdrantVectorStore", return_value=_vector_store_mock
)
_qvs_patch.start()

# ---------------------------------------------------------------------------
# Standard imports (after env vars and patches are in place)
# ---------------------------------------------------------------------------
import uuid
from typing import Any, Generator

import pytest
from collections.abc import AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessageChunk


# ---------------------------------------------------------------------------
# Deterministic fake returns for the two primary external I/O calls
# ---------------------------------------------------------------------------

_FAKE_DOCS = [
    Document(
        page_content="Die SPD setzt sich für ambitionierten Klimaschutz ein.",
        metadata={
            "document_name": "SPD Wahlprogramm 2025",
            "page": 0,
            "document_publish_date": "2025-01-01",
            "url": "https://www.spd.de/wahlprogramm",
            "source_document": "spd_wahlprogramm_2025.pdf",
        },
    ),
]

_FAKE_TOKENS = ["Hallo", " Welt"]

_FAKE_PARTY = {
    "party_id": "spd",
    "name": "SPD",
    "long_name": "Sozialdemokratische Partei Deutschlands",
    "manifesto_url": "https://www.spd.de/wahlprogramm",
    "candidate": "Olaf Scholz",
    "website_url": "https://www.spd.de",
    "is_already_in_parliament": True,
    "is_small_party": False,
    "description": "Die Sozialdemokratische Partei Deutschlands",
    "background_color": "#E3000F",
    "logo_src": "",
}


async def _fake_identify_relevant_docs(*args: Any, **kwargs: Any) -> list[Document]:
    """Deterministic Qdrant replacement — no embed or search calls."""
    return _FAKE_DOCS


_FAKE_ZERO_VECTOR = [0.0] * 3072  # matches EMBEDDING_DIM (text-embedding-3-large)


def _fake_retrieve(*args: Any, **kwargs: Any) -> list[dict]:
    """Deterministic retrieve() replacement — returns empty payload list."""
    return []


_FAKE_MANIFESTO_PAYLOAD = {
    "citation_title": "SPD Wahlprogramm 2025",
    "citation_url": "https://www.spd.de/wahlprogramm.pdf",
    "publish_date": "2025-01-01",
    "text": "Die SPD setzt sich für ambitionierten Klimaschutz ein.",
    "authority_tier": "self_reported",
    "meta": {"page_start": 1, "source_kind": "pdf"},
}


def _fake_retrieve_two_pass(query: str, **kwargs: Any) -> dict[str, list[dict]]:
    """Deterministic retrieve_two_pass() replacement.

    The default context resolves a term window (region ["DE"]), so the chat
    stream takes the TWO-PASS path — this patch makes that path deterministic
    instead of silently falling into _safe_two_pass's exception fallback.
    Returns one manifesto payload in the current bucket so sources_ready
    carries real two-pass content; other sources return empty buckets.
    """
    if kwargs.get("source_type") == "party_manifesto":
        return {"current": [dict(_FAKE_MANIFESTO_PAYLOAD)], "historic": []}
    return {"current": [], "historic": []}


async def _fake_stream_answer(
    *args: Any, **kwargs: Any
) -> AsyncIterator[AIMessageChunk]:
    """Deterministic LLM stream replacement — no external LLM call."""

    async def _gen() -> AsyncIterator[AIMessageChunk]:
        for token in _FAKE_TOKENS:
            yield AIMessageChunk(content=token)

    return _gen()


# ---------------------------------------------------------------------------
# Firebase / Firestore fake returns
# ---------------------------------------------------------------------------


async def _fake_aget_parties_for_context(context_id: str) -> list[Any]:
    from src.models.context import ContextParty

    return [ContextParty(**_FAKE_PARTY)]


async def _fake_aget_proposed_questions(context_id: str, party_id: str) -> list[str]:
    return []


async def _fake_aget_cached_answers(
    context_id: str, party_id: str, cache_key: str
) -> list[Any]:
    return []


async def _fake_awrite_cached_answer(*args: Any, **kwargs: Any) -> None:
    return None


async def _fake_aget_cached_rag_query(
    context_id: str, party_id: str, cache_key: str
) -> None:
    return None


async def _fake_awrite_cached_rag_query(*args: Any, **kwargs: Any) -> None:
    return None


async def _fake_awrite_llm_status(*args: Any, **kwargs: Any) -> None:
    return None


async def _fake_aget_context_by_id(context_id: str) -> None:
    return None


# ---------------------------------------------------------------------------
# LLM helper call fake returns
# ---------------------------------------------------------------------------


async def _fake_get_question_targets(*args: Any, **kwargs: Any):
    """Return: (party_id_list, general_question, is_comparing_question)."""
    return (["spd"], "Was ist die Position der SPD zum Klimaschutz?", False)


async def _fake_generate_improvement_rag_query(*args: Any, **kwargs: Any) -> str:
    return "SPD Klimaschutz Position"


class _FakeQuickReplies:
    quick_replies: list[str] = ["Wie finanziert die SPD das?", "Was sagt die CDU dazu?"]
    chat_title: str = "SPD Klimaschutz"


async def _fake_generate_chat_title_and_quick_replies(*args: Any, **kwargs: Any):
    return _FakeQuickReplies()


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def patch_chat_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch all external I/O calls in the chat stream.

    Primary patches (embed-once + retrieve() path):
      - src.chat_service.embed → mock with aembed_query returning a zero vector
          (identify_relevant_docs_with_llm_based_reranking was replaced with
          embed.aembed_query + retrieve(); this patch eliminates the OpenAI call)
      - src.chat_service.retrieve → returns [] (empty payloads; no Qdrant call)
      - src.chat_service.retrieve_two_pass → deterministic manifesto-only
          current bucket (the default context resolves a term window, so the
          chat stream takes the two-pass path)
      - src.chatbot_async.stream_answer_from_llms → deterministic token stream
          (eliminates live LLM / OpenAI / Gemini astream call)

    Secondary patches (required because generate_chat_stream also calls
    these Firestore and LLM helpers; all are "external I/O"):
      - src.chat_service.aget_parties_for_context
      - src.chat_service.aget_proposed_questions_for_context
      - src.chat_service.aget_cached_answers_for_party
      - src.chat_service.awrite_cached_answer_for_party
      - src.chat_service.aget_cached_rag_query
      - src.chat_service.awrite_cached_rag_query
      - src.llms.awrite_llm_status  (called by handle_rate_limit_hit)
      - src.chatbot_async.aget_context_by_id
      - src.chat_service.aget_context_by_id  (direct import for region_path fetch)
      - src.chatbot_async.get_question_targets_and_type
      - src.chatbot_async.generate_improvement_rag_query
      - src.chatbot_async.generate_chat_title_and_chick_replies

    Nothing in src/routes/chat.py, EventSourceResponse, or _frame() is
    touched — the real SSE generator, route, and framing run live.
    """
    # Primary patches — replace embed-once + retrieve() calls in chat_service.
    # The V1 identify_relevant_docs_with_llm_based_reranking call was removed;
    # the single-party path now calls embed.aembed_query() then asyncio.to_thread(retrieve, ...).
    # We patch both so the SSE smoke test requires no live OpenAI key or Qdrant.
    _fake_embed_mock = MagicMock()
    _fake_embed_mock.aembed_query = AsyncMock(return_value=_FAKE_ZERO_VECTOR)
    monkeypatch.setattr("src.chat_service.embed", _fake_embed_mock)
    monkeypatch.setattr("src.chat_service.retrieve", _fake_retrieve)
    # Both retrieval entry points must be patched: contexts that resolve a term
    # window use retrieve_two_pass, all others use retrieve. Patching only
    # retrieve would leave the two-pass path exercising the Qdrant mock via
    # _safe_two_pass's exception fallback instead of real framing.
    monkeypatch.setattr("src.chat_service.retrieve_two_pass", _fake_retrieve_two_pass)
    monkeypatch.setattr(
        "src.chatbot_async.stream_answer_from_llms",
        _fake_stream_answer,
    )

    # Firestore patches (secondary — no live Firestore)
    monkeypatch.setattr(
        "src.chat_service.aget_parties_for_context",
        _fake_aget_parties_for_context,
    )
    monkeypatch.setattr(
        "src.chat_service.aget_proposed_questions_for_context",
        _fake_aget_proposed_questions,
    )
    monkeypatch.setattr(
        "src.chat_service.aget_cached_answers_for_party",
        _fake_aget_cached_answers,
    )
    monkeypatch.setattr(
        "src.chat_service.awrite_cached_answer_for_party",
        _fake_awrite_cached_answer,
    )
    monkeypatch.setattr(
        "src.chat_service.aget_cached_rag_query",
        _fake_aget_cached_rag_query,
    )
    monkeypatch.setattr(
        "src.chat_service.awrite_cached_rag_query",
        _fake_awrite_cached_rag_query,
    )
    monkeypatch.setattr(
        "src.llms.awrite_llm_status",
        _fake_awrite_llm_status,
    )

    # LLM helper patches — patched at USE SITE in chat_service (not at definition
    # site in chatbot_async) because chat_service imports the names directly:
    #   from src.chatbot_async import get_question_targets_and_type, ...
    monkeypatch.setattr(
        "src.chat_service.get_question_targets_and_type",
        _fake_get_question_targets,
    )
    monkeypatch.setattr(
        "src.chat_service.generate_improvement_rag_query",
        _fake_generate_improvement_rag_query,
    )
    monkeypatch.setattr(
        "src.chat_service.generate_chat_title_and_chick_replies",
        _fake_generate_chat_title_and_quick_replies,
    )
    # aget_context_by_id is called inside chatbot_async.generate_improvement_rag_query
    # and generate_streaming_chatbot_response — patching the importers:
    monkeypatch.setattr(
        "src.chatbot_async.aget_context_by_id",
        _fake_aget_context_by_id,
    )
    # chat_service imports aget_context_by_id directly (region_path fetch at the
    # top of generate_chat_stream) — without this use-site patch the smoke test
    # makes a live Firestore call, which times out (~300s) in CI where no
    # emulator listens on FIRESTORE_EMULATOR_HOST.
    monkeypatch.setattr(
        "src.chat_service.aget_context_by_id",
        _fake_aget_context_by_id,
    )


# ===========================================================================
# Shared fixtures
# ===========================================================================

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def bundestag_vote_939() -> dict:
    """Load the bundestag_vote_939.json stub fixture (Pattern 4 raw dict shape).

    Shape: id, url, date, title, subtitle, detail_text, links,
           voting_results.overall, voting_results.by_party (≥3 parties).
    Used by: test_bundestag_connector.py.
    """
    return json.loads((_FIXTURES_DIR / "bundestag_vote_939.json").read_text())


@pytest.fixture()
def temp_qdrant_collection() -> "Generator[tuple, None, None]":
    """Create an isolated throwaway Qdrant collection and yield (client, name).

    Mirrors the temp_collection fixture in test_qdrant_schema.py.
    The collection is unconditionally deleted in the finally block to preserve
    wahlchat_chunks_dev's zero-chunk guarantee.

    IMPORTANT: this fixture is a no-op placeholder when Qdrant is not reachable
    — tests that depend on it must guard with their own module-level skip.
    Uses the real QdrantClient from qdrant_client.qdrant_client to bypass
    conftest's module-level MagicMock patch.
    """
    try:
        from qdrant_client.qdrant_client import QdrantClient as _RealQdrantClient
        from qdrant_client.models import Distance, VectorParams

        from src.ingestion.setup_collection import EMBEDDING_DIM

        client = _RealQdrantClient(url="http://localhost:6333", api_key=None)
        # Quick reachability check — skip fixture if Qdrant is down.
        client.get_collections()
    except Exception:  # noqa: BLE001
        pytest.skip("local Qdrant not reachable — run `make stores-up`")
        return  # unreachable; satisfies type checkers

    name = f"_test_tmp_{uuid.uuid4().hex[:8]}"
    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
        },
    )
    try:
        yield client, name
    finally:
        try:
            client.delete_collection(name)
        except Exception:  # noqa: BLE001
            pass  # best-effort cleanup
