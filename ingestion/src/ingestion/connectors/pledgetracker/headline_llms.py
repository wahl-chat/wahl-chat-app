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
from typing import Any

from langchain_core.messages import BaseMessage

from ingestion.llm_clients import RosterLLM as _LLM
from ingestion.llm_clients import gemini as _gemini
from ingestion.llm_clients import openai as _openai
from ingestion.llm_clients import structured_output_with_failover
from wahlchat_common.vertex_credentials import (
    vertex_enabled,
    vertex_location,
    vertex_project,
)

logger = logging.getLogger(__name__)


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
    from ingestion.firestore_client import firestore_client

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
    result, _ = await structured_output_with_failover(
        pre_post_llms(), messages, schema, on_primaries_exhausted=_mark_rate_limit
    )
    return result
