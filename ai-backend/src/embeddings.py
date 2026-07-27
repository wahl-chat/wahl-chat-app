# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Embeddings provider factory — single construction site for the embedding client.

Every place that needs an embeddings client (the ingestion runner, retrieve(),
and the legacy vector_store_helper) resolves it through ``get_embeddings()`` so
the provider can be swapped by configuration alone, without editing code.

Configuration (all optional; the defaults reproduce the current behaviour
EXACTLY — with no env set this returns OpenAI ``text-embedding-3-large`` @ 3072):

  EMBEDDING_PROVIDER   "openai" (default) | "gemini"
  EMBEDDING_MODEL      embedding model name — defaults to setup_collection's
                       value (the locked vector-space source of truth)
  EMBEDDING_DIM        output dimension — defaults to setup_collection's value;
                       forwarded to Gemini as ``output_dimensionality`` so the
                       vector width matches the collection and run.py's
                       per-vector dimension guard (_upsert_chunks).

Model and dimension default to ``EMBEDDING_MODEL`` / ``EMBEDDING_DIM`` in
``src.ingestion.setup_collection`` — the canonical vector-space definition — so
they stay in lockstep with the collection the vectors are written to.

Gemini reads its key from ``GOOGLE_API_KEY`` (falling back to ``GEMINI_API_KEY``)
for AI Studio access; OpenAI reads ``OPENAI_API_KEY`` from the environment as it
does today.
"""

from __future__ import annotations

import os
from typing import Optional

from langchain_core.embeddings import Embeddings

from src.ingestion.setup_collection import EMBEDDING_DIM, EMBEDDING_MODEL

_DEFAULT_PROVIDER = "openai"


def get_embeddings(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    output_dimensionality: Optional[int] = None,
    task_type: Optional[str] = None,
) -> Embeddings:
    """Return a LangChain embeddings client selected by configuration.

    Args:
        provider: Override the ``EMBEDDING_PROVIDER`` env value. When None the env
                  is read, defaulting to ``"openai"`` (current behaviour).
        model:    Override the embedding model name. When None it defaults to
                  ``EMBEDDING_MODEL`` (env-overridable via setup_collection).
        output_dimensionality: Override the vector dimension. When None it
                  defaults to ``EMBEDDING_DIM``. Only meaningful for Gemini, where
                  it is forwarded as ``output_dimensionality`` so the produced
                  vectors match the collection width.
        task_type: Gemini-only optimisation axis — how the embedding will be USED,
                  not a data format. Corpus passages (the ingestion runner) should
                  pass ``"RETRIEVAL_DOCUMENT"``; the search query (retrieve()) should
                  pass ``"RETRIEVAL_QUERY"``. The asymmetric document/query spaces
                  materially improve retrieval. Ignored for OpenAI (no such axis).
                  Baked into the vectors → set it correctly BEFORE ingesting.

    Returns:
        An ``Embeddings`` instance for the resolved provider.

    Raises:
        ValueError: If the resolved provider is neither "openai" nor "gemini".
    """
    resolved_provider = (
        (
            provider
            if provider is not None
            else os.getenv("EMBEDDING_PROVIDER", _DEFAULT_PROVIDER)
        )
        .strip()
        .lower()
    )
    resolved_model = model if model is not None else EMBEDDING_MODEL
    resolved_dim = (
        output_dimensionality if output_dimensionality is not None else EMBEDDING_DIM
    )

    if resolved_provider == "openai":
        # Default path — byte-for-byte the previous construction. The API key is
        # read from OPENAI_API_KEY by OpenAIEmbeddings itself, unchanged.
        from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

        return OpenAIEmbeddings(model=resolved_model)

    if resolved_provider == "gemini":
        # AI Studio access: GOOGLE_API_KEY is the primary name (matches llms.py);
        # GEMINI_API_KEY is accepted as an alias. output_dimensionality pins the
        # vector width to the collection so run.py's dimension guard passes.
        from langchain_google_genai import (  # noqa: PLC0415
            GoogleGenerativeAIEmbeddings,
        )

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return GoogleGenerativeAIEmbeddings(
            model=resolved_model,
            output_dimensionality=resolved_dim,
            google_api_key=api_key,
            task_type=task_type,
        )

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER {resolved_provider!r}; "
        "expected 'openai' or 'gemini'."
    )
