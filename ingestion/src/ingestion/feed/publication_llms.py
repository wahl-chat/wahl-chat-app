# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The roster for the parliament feed's one-time texts.

Summaries, headlines, party positions and translations are generated once and
then reused by every surface, so correctness on the first try outweighs
latency and cost: the chat's strongest flash models with high reasoning. No
flash-lite here. The timeout fits one debate's prompt; a model that takes
longer fails over to the next, and the builder's deadline cuts the failover
once the job's time budget is spent.

An exhausted roster does not touch ``system_status/llm_status``: that flag
tells chat users the service is degraded, and a batch run running out of
models says nothing about the chat's.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import BaseMessage

from ingestion.llm_clients import (
    RosterLLM,
    gemini,
    openai,
    structured_output_with_failover,
)
from wahlchat_common.vertex_credentials import (
    vertex_enabled,
    vertex_location,
    vertex_project,
)

logger = logging.getLogger(__name__)

PUBLICATION_THINKING = "high"
_TIMEOUT_S = 120


def _build_publication_llms() -> list[RosterLLM]:
    """Same models and order as the chat's answer roster, Vertex tier first."""
    roster = [
        RosterLLM(
            "google-gemini-3.6-flash-high",
            gemini(
                "gemini-3.6-flash",
                thinking_level=PUBLICATION_THINKING,
                timeout=_TIMEOUT_S,
            ),
            100,
        ),
        RosterLLM(
            "openai-gpt-5.6-terra-high",
            openai(
                "gpt-5.6-terra",
                temperature=1.0,
                reasoning_effort=PUBLICATION_THINKING,
                timeout=_TIMEOUT_S,
            ),
            90,
        ),
        RosterLLM(
            "google-gemini-3.7-flash-high",
            gemini(
                "gemini-3.7-flash",
                thinking_level=PUBLICATION_THINKING,
                timeout=_TIMEOUT_S,
            ),
            80,
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
        RosterLLM(
            "vertex-gemini-3.6-flash-high",
            gemini(
                "gemini-3.6-flash",
                vertex=True,
                thinking_level=PUBLICATION_THINKING,
                timeout=_TIMEOUT_S,
            ),
            200,
        ),
        RosterLLM(
            "vertex-gemini-3.7-flash-high",
            gemini(
                "gemini-3.7-flash",
                vertex=True,
                thinking_level=PUBLICATION_THINKING,
                timeout=_TIMEOUT_S,
            ),
            190,
        ),
    ] + roster


# One roster per process: the clients cache connections bound to the event
# loop they first ran on (see ``FeedBuilder``).
_roster: list[RosterLLM] | None = None


def publication_llms() -> list[RosterLLM]:
    global _roster
    if _roster is None:
        _roster = _build_publication_llms()
    return _roster


async def structured_output_from_publication_llms(
    messages: list[BaseMessage], schema: type
) -> tuple[Any, str]:
    """The parsed output and the name of the roster entry that wrote it."""
    return await structured_output_with_failover(publication_llms(), messages, schema)
