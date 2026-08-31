# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Embeddings provider factory — single construction site for the embedding client.

Every place that needs an embeddings client (retrieve(), chat_service,
and the legacy vector_store_helper) resolves it through ``get_embeddings()`` so
the provider can be swapped by configuration alone, without editing code.

Configuration (all optional; the defaults reproduce the current behaviour
EXACTLY — with no env set this returns ``gemini-embedding-2`` @ 3072):

  EMBEDDING_PROVIDER   "openai" (default) | "gemini"
  EMBEDDING_MODEL      embedding model name — defaults to setup_collection's
                       value (the locked vector-space source of truth)
  EMBEDDING_DIM        output dimension — defaults to setup_collection's value;
                       forwarded to Gemini as ``output_dimensionality`` so the
                       vector width matches the collection and run.py's
                       per-vector dimension guard (_upsert_chunks).

Model and dimension default to ``EMBEDDING_MODEL`` / ``EMBEDDING_DIM`` in
``src.corpus`` — the canonical vector-space definition — so
they stay in lockstep with the collection the vectors are written to.

Gemini reads its key from ``GOOGLE_API_KEY`` (falling back to ``GEMINI_API_KEY``)
for AI Studio access; OpenAI reads ``OPENAI_API_KEY`` from the environment as it
does today.

Gemini transport (AI Studio vs Vertex AI) is chosen separately from the provider
string. When a Vertex service-account key is configured (see
``src/vertex_credentials.py``) the Gemini client is built against Vertex so the
spend lands on the billing project; ``EMBEDDINGS_USE_VERTEX=0`` forces AI Studio.
The provider string stays ``"gemini"`` either way — it names the vector space,
which is identical across both backends, and it is stamped into the Qdrant
embedding-space fingerprint that ``setup_collection.check_fingerprint`` enforces.
"""

from __future__ import annotations

import os
from typing import Optional

from langchain_core.embeddings import Embeddings

from wahlchat_corpus.corpus import EMBEDDING_DIM, EMBEDDING_MODEL

_DEFAULT_PROVIDER = "openai"


def _vertex_embeddings_requested() -> bool:
    """Whether Gemini embeddings should be routed through Vertex AI.

    Opt-out rather than opt-in: when Vertex credentials are configured at all,
    embeddings follow chat onto the billing project. ``EMBEDDINGS_USE_VERTEX=0``
    forces them back to AI Studio — the manual kill-switch, since embeddings have
    no runtime failover (clients are bound once at module level in
    ``src/chat_service.py`` and ``src/retrieve.py``).
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
        provider: Override the ``EMBEDDING_PROVIDER`` env value. When None the env
                  is read, defaulting to ``"openai"`` (current behaviour).
        model:    Override the embedding model name. When None it defaults to
                  ``EMBEDDING_MODEL`` (env-overridable via setup_collection).
        output_dimensionality: Override the vector dimension. When None it
                  defaults to ``EMBEDDING_DIM``. Only meaningful for Gemini, where
                  it is forwarded as ``output_dimensionality`` so the produced
                  vectors match the collection width.
        task_type: Gemini-only optimisation axis — how the embedding will be USED,
                  not a data format. Corpus passages (written by the ingestion
                  package) are embedded with ``"RETRIEVAL_DOCUMENT"``; the search
                  query here (retrieve()) must
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
        #
        # Imports stay INSIDE the branch: tests/test_embeddings.py patches
        # GoogleGenerativeAIEmbeddings at its import source, which only works
        # while this import is lazy.
        from langchain_google_genai import (  # noqa: PLC0415
            GoogleGenerativeAIEmbeddings,
        )

        # Transport selection is deliberately INDEPENDENT of the provider string.
        # "gemini" names the VECTOR SPACE, and that space is unchanged: Vertex and
        # AI Studio serve the same model at the same dimension, only billing
        # differs. The provider string is stamped into the Qdrant embedding-space
        # fingerprint (setup_collection.expected_fingerprint) and
        # check_fingerprint() raises on any mismatch — encoding transport in it
        # would reject the existing corpus and force a full re-ingest.
        from wahlchat_corpus.vertex_credentials import (  # noqa: PLC0415
            get_vertex_credentials,
            vertex_enabled,
            vertex_location,
            vertex_project,
        )

        # The kill-switch is checked FIRST and that ordering is load-bearing:
        # short-circuiting means EMBEDDINGS_USE_VERTEX=0 never touches the
        # credential resolver, so deliberately opting out cannot trip a
        # misconfiguration warning — or, under VERTEX_REQUIRED, a raise.
        if _vertex_embeddings_requested() and vertex_enabled():
            return GoogleGenerativeAIEmbeddings(
                model=resolved_model,
                output_dimensionality=resolved_dim,
                task_type=task_type,
                # Pinned on both paths — see _gemini() in src/llms.py for why
                # leaving this to inference is not safe in either direction.
                vertexai=True,
                credentials=get_vertex_credentials(),
                # NOTE: unlike the chat class, GoogleGenerativeAIEmbeddings does
                # NOT derive `project` from the credentials object. vertex_enabled()
                # has already established that this resolves to a real value.
                project=vertex_project(),
                location=vertex_location(),
            )

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return GoogleGenerativeAIEmbeddings(
            model=resolved_model,
            output_dimensionality=resolved_dim,
            google_api_key=api_key,
            task_type=task_type,
            vertexai=False,  # safety pin — see _gemini() in src/llms.py
        )

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER {resolved_provider!r}; "
        "expected 'openai' or 'gemini'."
    )
