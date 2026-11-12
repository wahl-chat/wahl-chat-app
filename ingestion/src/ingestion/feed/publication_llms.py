# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The roster for the parliament feed's one-time texts.

Summaries, headlines, party positions and translations are generated once and
then reused by every surface, so correctness on the first try outweighs
latency and cost: the chat's strongest Gemini flash models with high
reasoning, and an OpenAI model as the last fallback. No flash-lite here. The timeout fits one debate's prompt; a model that takes
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
    ai_studio_enabled,
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
    """The chat's Gemini models, Vertex tier first, then the OpenAI fallback.
    Within each tier Gemini 3.7 leads: it writes the stronger one-time texts.

    The AI Studio entries need ``GOOGLE_API_KEY`` and join only when it is
    set: the scheduled job runs on Vertex alone.
    """
    roster = [
        # The fallback behind Gemini: a newer, cheaper model, at minimal
        # reasoning, where its first answer is already good enough.
        RosterLLM(
            "openai-gpt-6.1-terra-minimal",
            openai(
                "gpt-6.1-terra",
                temperature=1.0,
                reasoning_effort="minimal",
                timeout=_TIMEOUT_S,
            ),
            90,
        ),
    ]
    ai_studio = ai_studio_enabled()
    if ai_studio:
        roster += [
            RosterLLM(
                "google-gemini-3.7-flash-high",
                gemini(
                    "gemini-3.7-flash",
                    thinking_level=PUBLICATION_THINKING,
                    timeout=_TIMEOUT_S,
                ),
                100,
            ),
            RosterLLM(
                "google-gemini-3.6-flash-high",
                gemini(
                    "gemini-3.6-flash",
                    thinking_level=PUBLICATION_THINKING,
                    timeout=_TIMEOUT_S,
                ),
                80,
            ),
        ]
    if not vertex_enabled():
        if ai_studio:
            logger.warning(
                "Vertex AI not configured; Gemini traffic will bill Google AI Studio."
            )
        else:
            logger.warning(
                "Neither Vertex AI nor GOOGLE_API_KEY configured; "
                "the feed roster has no Gemini model."
            )
        return roster
    logger.info(
        "Vertex AI enabled for Gemini: project=%s location=%s (%s).",
        vertex_project(),
        vertex_location(),
        "Google AI Studio registered as fallback"
        if ai_studio
        else "no GOOGLE_API_KEY, so no AI Studio fallback",
    )
    return [
        RosterLLM(
            "vertex-gemini-3.7-flash-high",
            gemini(
                "gemini-3.7-flash",
                vertex=True,
                thinking_level=PUBLICATION_THINKING,
                timeout=_TIMEOUT_S,
            ),
            200,
        ),
        RosterLLM(
            "vertex-gemini-3.6-flash-high",
            gemini(
                "gemini-3.6-flash",
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
