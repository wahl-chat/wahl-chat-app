# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Factory for the embedding client.

The ingestion runner and ``retrieve()`` call ``get_embeddings()``.
Set ``EMBEDDING_PROVIDER`` to select the client.

Defaults when the variables are unset:

  EMBEDDING_PROVIDER   gemini
  EMBEDDING_MODEL      gemini-embedding-2
  EMBEDDING_DIM        3072

Model and dimension come from ``wahlchat_common.corpus``.
The fingerprint stores the same provider, model, and dimension.

``EMBEDDING_PROVIDER`` accepts ``gemini`` or ``openai``.
Gemini receives ``EMBEDDING_DIM`` as ``output_dimensionality``.
The runner rejects a vector whose width does not match the collection.

Gemini reads ``GOOGLE_API_KEY``, then ``GEMINI_API_KEY``.
OpenAI reads ``OPENAI_API_KEY``.

Vertex AI is a transport for the same vector space.
When Vertex credentials exist, the Gemini client uses Vertex.
Set ``EMBEDDINGS_USE_VERTEX=0`` to use AI Studio.
The provider string stays ``gemini`` on both transports.
``wahlchat_common.corpus.check_fingerprint`` compares the provider, not the transport.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from langchain_core.embeddings import Embeddings

from wahlchat_common.corpus import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    resolve_embedding_provider,
)


# On Vertex, every Gemini embedding model except gemini-embedding-001 is served by
# embedContent, which takes one content per request: google-genai rejects a batch
# before sending it. AI Studio accepts batches for the same models.
_VERTEX_BATCH_CAPABLE_MODELS = frozenset({"gemini-embedding-001"})
# Parallel requests per embed_documents call — enough to keep a long manifesto well
# inside a function timeout, far below the Vertex per-minute quota.
_VERTEX_MAX_PARALLEL_REQUESTS = 8


class _OneContentPerRequest(Embeddings):
    """Embeds each document in its own request, a bounded number in parallel."""

    def __init__(self, client: Embeddings, max_parallel: int) -> None:
        self.client = client
        self._max_parallel = max_parallel

    def _embed_one(self, text: str) -> list[float]:
        return self.client.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if len(texts) <= 1:
            return self.client.embed_documents(texts)
        workers = min(self._max_parallel, len(texts))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(self._embed_one, texts))

    def embed_query(self, text: str) -> list[float]:
        return self.client.embed_query(text)

    async def aembed_query(self, text: str) -> list[float]:
        return await self.client.aembed_query(text)


def _vertex_embeddings_requested() -> bool:
    """Return True when Gemini embeddings must use Vertex AI.

    Credentials select Vertex. ``EMBEDDINGS_USE_VERTEX=0`` selects AI Studio.
    The chat service and ``retrieve()`` create the client once.
    A change of this variable applies after the process starts again.
    """
    return os.getenv("EMBEDDINGS_USE_VERTEX", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def get_embeddings(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    output_dimensionality: Optional[int] = None,
    task_type: Optional[str] = None,
) -> Embeddings:
    """Return a LangChain embeddings client selected by configuration.

    Args:
        provider: Override ``EMBEDDING_PROVIDER``.
                  When None, ``resolve_embedding_provider()`` supplies the value.
                  The default is ``gemini``.
        model:    Override the model name. When None, use ``EMBEDDING_MODEL``.
        output_dimensionality: Override the vector width.
                  When None, use ``EMBEDDING_DIM``.
                  Gemini receives this value as ``output_dimensionality``.
        task_type: Gemini only. This value selects the embedding use.
                  Corpus passages use ``RETRIEVAL_DOCUMENT``.
                  ``retrieve()`` passes ``RETRIEVAL_QUERY`` for the search query.
                  OpenAI ignores this argument.
                  The value is part of the vector. Set it before ingestion.

    Returns:
        An ``Embeddings`` instance for the resolved provider.

    Raises:
        ValueError: If the resolved provider is neither "openai" nor "gemini".
    """
    resolved_provider = (
        provider.strip().lower()
        if provider is not None
        else resolve_embedding_provider()
    )
    resolved_model = model if model is not None else EMBEDDING_MODEL
    resolved_dim = (
        output_dimensionality if output_dimensionality is not None else EMBEDDING_DIM
    )

    if resolved_provider == "openai":
        # OpenAIEmbeddings reads OPENAI_API_KEY from the environment.
        from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

        return OpenAIEmbeddings(model=resolved_model)

    if resolved_provider == "gemini":
        # Import inside this branch.
        # Tests patch GoogleGenerativeAIEmbeddings on its source module.
        # A top-level import would bind the class before the patch.
        from langchain_google_genai import (  # noqa: PLC0415
            GoogleGenerativeAIEmbeddings,
        )

        # "gemini" names the vector space, not the transport.
        # Vertex and AI Studio use the same model and the same dimension.
        # The fingerprint stores the provider. It does not store the transport.
        from wahlchat_common.vertex_credentials import (  # noqa: PLC0415
            get_vertex_credentials,
            vertex_enabled,
            vertex_location,
            vertex_project,
        )

        # Check the kill switch first.
        # EMBEDDINGS_USE_VERTEX=0 must not call the credential resolver.
        # A call would log a misconfiguration, or raise when VERTEX_REQUIRED is set.
        if _vertex_embeddings_requested() and vertex_enabled():
            vertex_client = GoogleGenerativeAIEmbeddings(
                model=resolved_model,
                output_dimensionality=resolved_dim,
                task_type=task_type,
                # Set vertexai on both paths.
                # The client also reads GOOGLE_GENAI_USE_VERTEXAI.
                # That variable overrides inference from credentials.
                # An explicit value prevents the override.
                vertexai=True,
                credentials=get_vertex_credentials(),
                # GoogleGenerativeAIEmbeddings does not read project from credentials.
                # vertex_enabled() has already required a project id.
                project=vertex_project(),
                location=vertex_location(),
            )
            if resolved_model in _VERTEX_BATCH_CAPABLE_MODELS:
                return vertex_client
            return _OneContentPerRequest(vertex_client, _VERTEX_MAX_PARALLEL_REQUESTS)

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return GoogleGenerativeAIEmbeddings(
            model=resolved_model,
            output_dimensionality=resolved_dim,
            google_api_key=api_key,
            task_type=task_type,
            vertexai=False,
        )

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER {resolved_provider!r}; "
        "expected 'openai' or 'gemini'."
    )
