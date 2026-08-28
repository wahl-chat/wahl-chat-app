# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import logging
import os
from typing import AsyncIterator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_core.messages.base import BaseMessage, BaseMessageChunk
from pydantic import BaseModel
from src.firebase_service import awrite_llm_status
from ingestion.vertex_credentials import (
    get_vertex_credentials,
    vertex_enabled,
    vertex_location,
    vertex_project,
)
from src.models.general import LLM, LLMSize
from src.utils import load_env, safe_load_api_key

load_env()

logger = logging.getLogger(__name__)

# Vertex AI routing. Resolved once at import: when a service-account key for the
# billing project is configured, the Gemini models below are also constructed
# against Vertex and registered at a HIGHER priority than their AI Studio twins,
# so Gemini spend lands on that project. Absent credentials, VERTEX_AVAILABLE is
# False and the LLM lists are exactly what they were before — that is the local
# dev / CI path, and the reason nothing here may raise.
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


azure_gpt_4o = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    deployment_name="gpt-4o-2024-08-06",
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=safe_load_api_key("AZURE_OPENAI_API_KEY"),
    max_retries=0,
)

azure_gpt_4o_mini = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    deployment_name="gpt-4o-mini-2024-07-18",
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=safe_load_api_key("AZURE_OPENAI_API_KEY"),
    max_retries=0,
)

google_gemini_2_flash = _gemini("gemini-2.0-flash")

google_gemini_3_flash_preview = _gemini(
    "gemini-3-flash-preview",
    temperature=1.0,  # Explicitly set temperature to 1.0 based on Google's recommendation in https://ai.google.dev/gemini-api/docs/gemini-3#temperature,
    thinking_level="low",  # Set thinking level to low for faster responses
)

google_gemini_2_5_flash = _gemini(
    "gemini-2.5-flash",
    thinking_budget=0,  # Disable thinking budget for faster responses
)

openai_gpt_4o = ChatOpenAI(
    model="gpt-4o-2024-08-06",
    api_key=safe_load_api_key("OPENAI_API_KEY"),
    max_retries=0,
)

openai_gpt_4o_mini = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=safe_load_api_key("OPENAI_API_KEY"),
    max_retries=0,
)

RESPONSE_GENERATION_LLMS: list[LLM] = [
    LLM(
        name="google-gemini-3.0-flash-preview",
        model=google_gemini_3_flash_preview,
        sizes=[LLMSize.SMALL, LLMSize.LARGE],
        priority=100,
        is_at_rate_limit=False,
    ),
    LLM(
        name="google-gemini-2.5-flash",
        model=google_gemini_2_5_flash,
        sizes=[LLMSize.SMALL, LLMSize.LARGE],
        priority=95,
        is_at_rate_limit=False,
    ),
    LLM(
        name="google-gemini-2.0-flash",
        model=google_gemini_2_flash,
        sizes=[LLMSize.SMALL, LLMSize.LARGE],
        priority=92,
        is_at_rate_limit=False,
    ),
    LLM(
        name="azure-gpt-4o",
        model=azure_gpt_4o,
        sizes=[LLMSize.LARGE],
        priority=90,
        is_at_rate_limit=False,
        premium_only=True,
    ),
    LLM(
        name="openai-gpt-4o",
        model=openai_gpt_4o,
        sizes=[LLMSize.LARGE],
        priority=60,
        is_at_rate_limit=False,
        premium_only=False,
    ),
    LLM(
        name="azure-gpt-4o-mini",
        model=azure_gpt_4o_mini,
        sizes=[LLMSize.SMALL],
        priority=50,
        is_at_rate_limit=False,
    ),
    LLM(
        name="openai-gpt-4o-mini",
        model=openai_gpt_4o_mini,
        sizes=[LLMSize.SMALL],
        priority=40,
        is_at_rate_limit=False,
    ),
]

# Vertex tier — the same Gemini models, billed to the Vertex project. Priorities
# sit above every AI Studio entry (highest existing: 100), so the priority-sorted
# failover already in get_answer_from_llms / get_structured_output_from_llms /
# stream_answer_from_llms tries Vertex first and falls through to the IDENTICAL
# AI Studio model on any error. No change to those functions is required.
#
# gemini-2.0-flash is deliberately absent: it 404s on the billing project in
# every location tested (global, europe-west3/4, us-central1). Registering it
# would 404 on every request and silently fall through to AI Studio — the failure
# mode that looks like "Vertex billing is mysteriously low" rather than an error.
# Its AI Studio twin below still serves, so nothing is lost.
if VERTEX_AVAILABLE:
    RESPONSE_GENERATION_LLMS = [
        LLM(
            name="vertex-gemini-3.0-flash-preview",
            model=_gemini(
                "gemini-3-flash-preview",
                vertex=True,
                temperature=1.0,
                thinking_level="low",
            ),
            sizes=[LLMSize.SMALL, LLMSize.LARGE],
            priority=200,
            is_at_rate_limit=False,
        ),
        LLM(
            name="vertex-gemini-2.5-flash",
            model=_gemini("gemini-2.5-flash", vertex=True, thinking_budget=0),
            sizes=[LLMSize.SMALL, LLMSize.LARGE],
            priority=195,
            is_at_rate_limit=False,
        ),
    ] + RESPONSE_GENERATION_LLMS

azure_gpt_4o_mini_det = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    deployment_name="gpt-4o-mini-2024-07-18",
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    api_key=safe_load_api_key("AZURE_OPENAI_API_KEY"),
    temperature=0.0,
    max_retries=0,
)

google_gemini_2_5_flash_lite_det = _gemini("gemini-2.5-flash-lite", temperature=0.0)

google_gemini_2_flash_det = _gemini("gemini-2.0-flash", temperature=0.0)

openai_gpt_4o_mini_det = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=safe_load_api_key("OPENAI_API_KEY"),
    temperature=0.0,
    max_retries=0,
)

PRE_AND_POST_PROCESSING_LLMS: list[LLM] = [
    LLM(
        name="google-gemini-2.5-flash-lite-det",
        model=google_gemini_2_5_flash_lite_det,
        sizes=[LLMSize.SMALL],
        priority=100,
        is_at_rate_limit=False,
    ),
    LLM(
        name="google-gemini-2.0-flash-det",
        model=google_gemini_2_flash_det,
        sizes=[LLMSize.SMALL, LLMSize.LARGE],
        priority=95,
        is_at_rate_limit=False,
    ),
    LLM(
        name="azure-gpt-4o-mini-det",
        model=azure_gpt_4o_mini_det,
        sizes=[LLMSize.SMALL],
        priority=90,
        is_at_rate_limit=False,
    ),
    LLM(
        name="openai-gpt-4o-mini-det",
        model=openai_gpt_4o_mini_det,
        sizes=[LLMSize.SMALL],
        priority=80,
        is_at_rate_limit=False,
    ),
]

# Vertex tier for pre/post-processing — same rationale as above, and likewise
# without gemini-2.0-flash. gemini-2.5-flash covers the LARGE size here so the
# deterministic path is not left Vertex-less when a caller asks for it.
if VERTEX_AVAILABLE:
    PRE_AND_POST_PROCESSING_LLMS = [
        LLM(
            name="vertex-gemini-2.5-flash-lite-det",
            model=_gemini("gemini-2.5-flash-lite", vertex=True, temperature=0.0),
            sizes=[LLMSize.SMALL],
            priority=200,
            is_at_rate_limit=False,
        ),
        LLM(
            name="vertex-gemini-2.5-flash-det",
            model=_gemini("gemini-2.5-flash", vertex=True, temperature=0.0),
            sizes=[LLMSize.SMALL, LLMSize.LARGE],
            priority=195,
            is_at_rate_limit=False,
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
            response = await llm.model.ainvoke(messages)
            llm.is_at_rate_limit = False
            return response
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            llm.is_at_rate_limit = True
            continue

    await handle_rate_limit_hit_for_all_llms()

    for llm in back_up_llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            response = await llm.model.ainvoke(messages)
            llm.is_at_rate_limit = False
            return response
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            llm.is_at_rate_limit = True
    raise Exception("All LLMs are at rate limit.")


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
            response = await prepared_model.ainvoke(messages)
            llm.is_at_rate_limit = False
            return response
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            llm.is_at_rate_limit = True
            # TODO: consider writing to Firestore that this LLM now is at rate limit
            continue

    await handle_rate_limit_hit_for_all_llms()

    for llm in back_up_llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            prepared_model = llm.model.with_structured_output(schema)
            response = await prepared_model.ainvoke(messages)
            llm.is_at_rate_limit = False
            return response
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            llm.is_at_rate_limit = True
    raise Exception("All LLMs are at rate limit.")


async def stream_answer_from_llms(
    llms: list[LLM],
    messages: list[BaseMessage],
    preferred_llm_size: LLMSize = LLMSize.LARGE,
    use_premium_llms: bool = False,
) -> AsyncIterator[BaseMessageChunk]:
    logger.debug(f"Preferred LLM size: {preferred_llm_size}")
    if not use_premium_llms:
        llms = [llm for llm in llms if not llm.premium_only]
    if preferred_llm_size == LLMSize.LARGE:
        large_llms = [llm for llm in llms if LLMSize.LARGE in llm.sizes]
        small_llms = [
            llm
            for llm in llms
            if LLMSize.SMALL in llm.sizes and LLMSize.LARGE not in llm.sizes
        ]
        large_llms = sorted(large_llms, key=lambda x: x.priority, reverse=True)
        small_llms = sorted(small_llms, key=lambda x: x.priority, reverse=True)
        llms = large_llms + small_llms
    elif preferred_llm_size == LLMSize.SMALL:
        small_llms = [llm for llm in llms if LLMSize.SMALL in llm.sizes]
        large_llms = [
            llm
            for llm in llms
            if LLMSize.LARGE in llm.sizes and LLMSize.SMALL not in llm.sizes
        ]
        large_llms = sorted(large_llms, key=lambda x: x.priority, reverse=True)
        small_llms = sorted(small_llms, key=lambda x: x.priority, reverse=True)
        llms = small_llms + large_llms
    else:
        raise ValueError(f"Invalid preferred LLM size: {preferred_llm_size}")
    for llm in llms:
        try:
            logger.debug(f"Invoking LLM {llm.name}...")
            response = llm.model.astream(messages)
            llm.is_at_rate_limit = False
            return response
        except Exception as e:
            logger.warning(f"Error invoking LLM {llm.name}: {e}")
            llm.is_at_rate_limit = True
            continue

    return await handle_rate_limit_hit_for_all_llms()
