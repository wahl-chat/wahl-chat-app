# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Pre/post-processing LLM failover for pledge headline generation.

Ingestion cannot import the chat service, but short titles must use the same
roster the chat pre/post step uses: the same models, the same generation
settings, Vertex first when it is configured, and the same
``system_status/llm_status`` flag when every primary model fails. This module
is that roster. It is not the chat answer path.
"""

from __future__ import annotations

import logging
import os
from typing import Any, NamedTuple, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import SecretStr

from wahlchat_common.gemini_params import without_deprecated_generation_params
from wahlchat_common.vertex_credentials import (
    get_vertex_credentials,
    vertex_enabled,
    vertex_location,
    vertex_project,
)

logger = logging.getLogger(__name__)


class _LLM(NamedTuple):
    name: str
    model: BaseChatModel
    priority: int
    back_up_only: bool = False


def _api_key(name: str) -> Optional[SecretStr]:
    key = os.getenv(name)
    if not key:
        return None
    return SecretStr(key)


def _gemini(model: str, *, vertex: bool = False, **kwargs: Any) -> Any:
    """Same pin as the chat roster: ``vertexai`` is explicit on both paths.

    An unpinned client follows ``GOOGLE_GENAI_USE_VERTEXAI``, which would
    send the AI Studio fallback at Vertex (no credentials) or drop the Vertex
    tier onto AI Studio (no API key).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    # The API rejects these fields on Gemini 3.6 and later.
    # LangChain does not remove them for every affected model.
    kwargs = without_deprecated_generation_params(model, kwargs)

    if vertex:
        return ChatGoogleGenerativeAI(
            model=model,
            max_retries=0,
            vertexai=True,
            credentials=get_vertex_credentials(),
            project=vertex_project(),
            location=vertex_location(),
            labels={"app": "wahl-chat", "tier": "vertex"},
            **kwargs,
        )
    return ChatGoogleGenerativeAI(
        model=model,
        max_retries=0,
        api_key=_api_key("GOOGLE_API_KEY"),
        vertexai=False,
        **kwargs,
    )


def _openai(model: str, **kwargs: Any) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=_api_key("OPENAI_API_KEY"),
        max_retries=0,
        **kwargs,
    )


def _build_pre_post_llms() -> list[_LLM]:
    """The chat pre/post roster, Vertex tier first when credentials exist."""
    roster = [
        _LLM(
            "google-gemini-3.1-flash-lite",
            _gemini("gemini-3.1-flash-lite", temperature=1.0, thinking_level="minimal"),
            100,
        ),
        _LLM(
            "openai-gpt-5.6-luna",
            _openai("gpt-5.6-luna", temperature=1.0, reasoning_effort="minimal"),
            90,
        ),
        _LLM(
            "google-gemini-2.5-flash-lite",
            _gemini("gemini-2.5-flash-lite", temperature=1.0, thinking_budget=0),
            80,
        ),
        _LLM(
            "google-gemini-3.5-flash-lite",
            _gemini("gemini-3.5-flash-lite", thinking_level="minimal"),
            70,
        ),
    ]
    if not vertex_enabled():
        logger.warning(
            "Vertex AI not configured; Gemini traffic will bill Google AI Studio."
        )
        return roster
    logger.info(
        "Vertex AI enabled for Gemini: project=%s location=%s "
        "(Google AI Studio remains registered as fallback).",
        vertex_project(),
        vertex_location(),
    )
    return [
        _LLM(
            "vertex-gemini-3.1-flash-lite",
            _gemini(
                "gemini-3.1-flash-lite",
                vertex=True,
                temperature=1.0,
                thinking_level="minimal",
            ),
            200,
        ),
        _LLM(
            "vertex-gemini-2.5-flash-lite",
            _gemini(
                "gemini-2.5-flash-lite",
                vertex=True,
                temperature=1.0,
                thinking_budget=0,
            ),
            190,
        ),
        _LLM(
            "vertex-gemini-3.5-flash-lite",
            _gemini(
                "gemini-3.5-flash-lite",
                vertex=True,
                thinking_level="minimal",
            ),
            180,
        ),
    ] + roster


# One roster per process, matching the chat service: the clients cache
# connections bound to the loop they first ran on, so rebuilding them per
# pledge would drop that cache (and re-log the Vertex line every pledge).
_roster: list[_LLM] | None = None


def pre_post_llms() -> list[_LLM]:
    global _roster
    if _roster is None:
        _roster = _build_pre_post_llms()
    return _roster


def _mark_rate_limit() -> None:
    """Same flag the chat failover writes when every primary model has failed."""
    from ingestion.connectors.pledgetracker.firestore_client import firestore_client

    firestore_client().collection("system_status").document("llm_status").set(
        {"is_at_rate_limit": True}
    )


async def structured_output_from_pre_post_llms(
    messages: list[BaseMessage], schema: type
) -> Any:
    """Run ``schema`` against the pre/post roster, highest priority first.

    On exhaustion of the primary tier, stamp the rate-limit flag and then try
    backup-only models. Raises when nothing succeeded — callers that must not
    fail the run catch that.
    """
    llms = sorted(pre_post_llms(), key=lambda item: item.priority, reverse=True)
    backups = [llm for llm in llms if llm.back_up_only]
    primaries = [llm for llm in llms if not llm.back_up_only]
    for llm in primaries:
        try:
            logger.debug("Invoking LLM %s...", llm.name)
            prepared = llm.model.with_structured_output(schema)
            return await prepared.ainvoke(messages)
        except Exception as exc:
            logger.warning("Error invoking LLM %s: %s", llm.name, exc)
            continue

    _mark_rate_limit()

    for llm in backups:
        try:
            logger.debug("Invoking LLM %s...", llm.name)
            prepared = llm.model.with_structured_output(schema)
            return await prepared.ainvoke(messages)
        except Exception as exc:
            logger.warning("Error invoking LLM %s: %s", llm.name, exc)
    raise Exception("All LLMs failed.")
