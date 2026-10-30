# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""LLM client builders and failover shared by the ingestion rosters.

Ingestion cannot import the chat service, so each runner that needs an LLM
keeps its own roster (PledgeTracker headlines, the parliament feed). The way a
client is built and the way a roster fails over live here once, so the
rosters cannot drift apart on Vertex pinning or deprecated parameters.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, NamedTuple, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import SecretStr

from wahlchat_common.gemini_params import without_deprecated_generation_params
from wahlchat_common.vertex_credentials import (
    get_vertex_credentials,
    vertex_location,
    vertex_project,
)

logger = logging.getLogger(__name__)


class RosterLLM(NamedTuple):
    name: str
    model: BaseChatModel
    priority: int
    back_up_only: bool = False


def api_key(name: str) -> Optional[SecretStr]:
    key = os.getenv(name)
    if not key:
        return None
    return SecretStr(key)


def gemini(model: str, *, vertex: bool = False, **kwargs: Any) -> Any:
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
        api_key=api_key("GOOGLE_API_KEY"),
        vertexai=False,
        **kwargs,
    )


def openai(model: str, **kwargs: Any) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key("OPENAI_API_KEY"),
        max_retries=0,
        **kwargs,
    )


async def structured_output_with_failover(
    roster: list[RosterLLM],
    messages: list[BaseMessage],
    schema: type,
    *,
    on_primaries_exhausted: Optional[Callable[[], None]] = None,
) -> tuple[Any, str]:
    """Run ``schema`` against ``roster``, highest priority first.

    Returns the parsed output and the name of the entry that produced it.
    ``on_primaries_exhausted`` runs once every primary model has failed,
    before the backup-only models are tried. Raises when nothing succeeded.
    """
    llms = sorted(roster, key=lambda item: item.priority, reverse=True)
    backups = [llm for llm in llms if llm.back_up_only]
    primaries = [llm for llm in llms if not llm.back_up_only]
    for llm in primaries:
        try:
            logger.debug("Invoking LLM %s...", llm.name)
            prepared = llm.model.with_structured_output(schema)
            return await prepared.ainvoke(messages), llm.name
        except Exception as exc:
            logger.warning("Error invoking LLM %s: %s", llm.name, exc)
            continue

    if on_primaries_exhausted is not None:
        on_primaries_exhausted()

    for llm in backups:
        try:
            logger.debug("Invoking LLM %s...", llm.name)
            prepared = llm.model.with_structured_output(schema)
            return await prepared.ainvoke(messages), llm.name
        except Exception as exc:
            logger.warning("Error invoking LLM %s: %s", llm.name, exc)
    raise Exception("All LLMs failed.")
