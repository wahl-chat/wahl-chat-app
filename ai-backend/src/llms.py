# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import logging
from typing import AsyncIterator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages.base import BaseMessage, BaseMessageChunk
from pydantic import BaseModel
from src.firebase_service import awrite_llm_status
from src.google_credentials import (
    get_vertex_credentials,
    vertex_enabled,
    vertex_location,
    vertex_project,
)
from src.models.general import LLM
from src.utils import load_env, safe_load_api_key

load_env()

logger = logging.getLogger(__name__)

# Vertex AI routing. Resolved once at import: when a service-account key for the
# billing project is configured, the Gemini models below are also constructed
# against Vertex and registered at a HIGHER priority than their AI Studio twins,
# so Gemini spend lands on that project. Absent credentials, VERTEX_AVAILABLE is
# False and the LLM lists are exactly the AI Studio / OpenAI roster — that is the
# local dev / CI path, and the reason nothing here may raise.
VERTEX_AVAILABLE = vertex_enabled()
_VERTEX_CREDS = get_vertex_credentials() if VERTEX_AVAILABLE else None
_VERTEX_PROJECT = vertex_project() if VERTEX_AVAILABLE else None

# One line at import, so which backend a revision actually came up on is
# answerable from the logs alone. Without it, the only symptom of a Vertex tier
# that failed to register is billing that never moves.
if VERTEX_AVAILABLE:
    logger.info(
        "Vertex AI enabled for Gemini: project=%s location=%s "
        "(Google AI Studio remains registered as fallback).",
        _VERTEX_PROJECT,
        vertex_location(),
    )
else:
    logger.warning(
        "Vertex AI not configured; Gemini traffic will bill Google AI Studio."
    )


def _gemini(model: str, *, vertex: bool = False, **kwargs) -> ChatGoogleGenerativeAI:
    """Construct a Gemini client against either backend.

    Both backends are the same class: langchain-google-genai speaks Vertex and AI
    Studio from one ChatGoogleGenerativeAI, so no separate ChatVertexAI is
    involved and model kwargs such as ``thinking_level`` / ``thinking_budget``
    carry over unchanged.

    ``vertexai`` is pinned explicitly on BOTH paths, and that is load-bearing
    rather than decorative. _determine_backend resolves the backend in priority
    order: the explicit ``vertexai`` argument, then GOOGLE_GENAI_USE_VERTEXAI,
    then the presence of ``credentials``, then ``project``, then AI Studio. The
    env var therefore outranks credential-based inference in both directions:

      - unpinned AI Studio client + GOOGLE_GENAI_USE_VERTEXAI=true  -> silently
        targets Vertex and fails for want of credentials, collapsing the fallback
        exactly when it is needed;
      - unpinned Vertex client  + GOOGLE_GENAI_USE_VERTEXAI=false -> silently
        drops to AI Studio carrying no API key at all.

    Nothing in this repo sets that variable, which is the point: pinning both ends
    means nothing outside the repo can repoint either tier either.
    """
    if vertex:
        return ChatGoogleGenerativeAI(
            model=model,
            max_retries=0,
            vertexai=True,
            credentials=_VERTEX_CREDS,
            project=_VERTEX_PROJECT,
            location=vertex_location(),
            # Surfaces in Cloud Billing reports for per-app attribution.
            labels={"app": "wahl-chat", "tier": "vertex"},
            **kwargs,
        )
    return ChatGoogleGenerativeAI(
        model=model,
        max_retries=0,
        api_key=safe_load_api_key("GOOGLE_API_KEY"),
        vertexai=False,
        **kwargs,
    )


def _openai(model: str, **kwargs) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=safe_load_api_key("OPENAI_API_KEY"),
        max_retries=0,
        **kwargs,
    )


def _llm(name: str, model: BaseChatModel, priority: int) -> LLM:
    return LLM(name=name, model=model, priority=priority)


# ---------------------------------------------------------------------------
# Response generation — temperature 1 on every model.
# Gemini 3.6 Flash is the primary; 3.7 Flash does not support thinking_level
# "minimal", so it uses "low". Gemini 2.5-era models are not on this roster.
# ---------------------------------------------------------------------------
google_gemini_3_6_flash = _gemini(
    "gemini-3.6-flash", temperature=1.0, thinking_level="minimal"
)
google_gemini_3_7_flash = _gemini(
    "gemini-3.7-flash", temperature=1.0, thinking_level="low"
)
google_gemini_3_flash_preview = _gemini(
    "gemini-3-flash-preview", temperature=1.0, thinking_level="minimal"
)
google_gemini_3_5_flash = _gemini(
    "gemini-3.5-flash", temperature=1.0, thinking_level="minimal"
)
openai_gpt_5_6_terra = _openai(
    "gpt-5.6-terra", temperature=1.0, reasoning_effort="minimal"
)

RESPONSE_GENERATION_LLMS: list[LLM] = [
    _llm("google-gemini-3.6-flash", google_gemini_3_6_flash, 100),
    _llm("openai-gpt-5.6-terra", openai_gpt_5_6_terra, 90),
    _llm("google-gemini-3.7-flash", google_gemini_3_7_flash, 80),
    _llm("google-gemini-3-flash-preview", google_gemini_3_flash_preview, 70),
    _llm("google-gemini-3.5-flash", google_gemini_3_5_flash, 60),
]

# Vertex tier — the same Gemini models, billed to the Vertex project. Priorities
# sit above every AI Studio / OpenAI entry (highest existing: 100), so the
# priority-sorted failover already in get_answer_from_llms /
# get_structured_output_from_llms / stream_answer_from_llms tries Vertex first
# and falls through to the IDENTICAL AI Studio model on any error. No change to
# those functions is required. OpenAI models have no Vertex twin.
if VERTEX_AVAILABLE:
    RESPONSE_GENERATION_LLMS = [
        _llm(
            "vertex-gemini-3.6-flash",
            _gemini(
                "gemini-3.6-flash",
                vertex=True,
                temperature=1.0,
                thinking_level="minimal",
            ),
            200,
        ),
        _llm(
            "vertex-gemini-3.7-flash",
            _gemini(
                "gemini-3.7-flash",
                vertex=True,
                temperature=1.0,
                thinking_level="low",
            ),
            190,
        ),
        _llm(
            "vertex-gemini-3-flash-preview",
            _gemini(
                "gemini-3-flash-preview",
                vertex=True,
                temperature=1.0,
                thinking_level="minimal",
            ),
            180,
        ),
        _llm(
            "vertex-gemini-3.5-flash",
            _gemini(
                "gemini-3.5-flash",
                vertex=True,
                temperature=1.0,
                thinking_level="minimal",
            ),
            170,
        ),
    ] + RESPONSE_GENERATION_LLMS

# ---------------------------------------------------------------------------
# Pre- and post-processing — temperature 1, minimal reasoning on every model.
# Gemini 2.5 Flash-Lite has no thinking_level; thinking_budget=0 is the 2.5
# equivalent of minimal/off thinking.
# ---------------------------------------------------------------------------
google_gemini_3_1_flash_lite = _gemini(
    "gemini-3.1-flash-lite", temperature=1.0, thinking_level="minimal"
)
google_gemini_2_5_flash_lite = _gemini(
    "gemini-2.5-flash-lite", temperature=1.0, thinking_budget=0
)
google_gemini_3_5_flash_lite = _gemini(
    "gemini-3.5-flash-lite", temperature=1.0, thinking_level="minimal"
)
openai_gpt_5_6_luna = _openai(
    "gpt-5.6-luna", temperature=1.0, reasoning_effort="minimal"
)

PRE_AND_POST_PROCESSING_LLMS: list[LLM] = [
    _llm("google-gemini-3.1-flash-lite", google_gemini_3_1_flash_lite, 100),
    _llm("openai-gpt-5.6-luna", openai_gpt_5_6_luna, 90),
    _llm("google-gemini-2.5-flash-lite", google_gemini_2_5_flash_lite, 80),
    _llm("google-gemini-3.5-flash-lite", google_gemini_3_5_flash_lite, 70),
]

if VERTEX_AVAILABLE:
    PRE_AND_POST_PROCESSING_LLMS = [
        _llm(
            "vertex-gemini-3.1-flash-lite",
            _gemini(
                "gemini-3.1-flash-lite",
                vertex=True,
                temperature=1.0,
                thinking_level="minimal",
            ),
            200,
        ),
        _llm(
            "vertex-gemini-2.5-flash-lite",
            _gemini(
                "gemini-2.5-flash-lite",
                vertex=True,
                temperature=1.0,
                thinking_budget=0,
            ),
            190,
        ),
        _llm(
            "vertex-gemini-3.5-flash-lite",
            _gemini(
                "gemini-3.5-flash-lite",
                vertex=True,
                temperature=1.0,
                thinking_level="minimal",
            ),
            180,
        ),
    ] + PRE_AND_POST_PROCESSING_LLMS


async def handle_rate_limit_hit_for_all_llms():
    await awrite_llm_status(is_at_rate_limit=True)


async def get_answer_from_llms(
    llms: list[LLM], messages: list[BaseMessage]
) -> BaseMessage:
    llms = sorted(llms, key=lambda x: x.priority, reverse=True)
    back_up_llms = [llm for llm in llms if llm.back_up_only]
    llms = [llm for llm in llms if not llm.back_up_only]
    for llm in llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            return await llm.model.ainvoke(messages)
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            continue

    await handle_rate_limit_hit_for_all_llms()

    for llm in back_up_llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            return await llm.model.ainvoke(messages)
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
    raise Exception("All LLMs failed.")


async def get_structured_output_from_llms(
    llms: list[LLM], messages: list[BaseMessage], schema: dict | type
) -> dict | BaseModel:
    llms = sorted(llms, key=lambda x: x.priority, reverse=True)
    back_up_llms = [llm for llm in llms if llm.back_up_only]
    llms = [llm for llm in llms if not llm.back_up_only]
    for llm in llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            prepared_model = llm.model.with_structured_output(schema)
            return await prepared_model.ainvoke(messages)
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            continue

    await handle_rate_limit_hit_for_all_llms()

    for llm in back_up_llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            prepared_model = llm.model.with_structured_output(schema)
            return await prepared_model.ainvoke(messages)
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
    raise Exception("All LLMs failed.")


def select_streaming_llms(llms: list[LLM]) -> list[LLM]:
    """Models ``stream_answer_from_llms`` will try, in failover order.

    The answer cache uses this list. A model or temperature change must
    change the key.
    """
    return sorted(llms, key=lambda x: x.priority, reverse=True)


async def stream_answer_from_llms(
    llms: list[LLM],
    messages: list[BaseMessage],
) -> AsyncIterator[BaseMessageChunk]:
    llms = select_streaming_llms(llms)
    for llm in llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            return llm.model.astream(messages)
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            continue

    return await handle_rate_limit_hit_for_all_llms()
