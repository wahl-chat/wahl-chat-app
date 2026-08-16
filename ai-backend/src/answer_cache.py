# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Exact-match cache key for curated (proposed-question) party answers.

A cached answer is replayed only when every input to the answer LLM matches:
question, preceding conversation, prompt templates and stable variables,
retrieved RAG context, and the generation roster (model, temperature, …).
The clock injected into the live system prompt (``{date}`` / ``{time}``) is
deliberately omitted so two otherwise-identical requests a minute apart can
still hit.
"""

from __future__ import annotations

import hashlib

from langchain_core.language_models.chat_models import BaseChatModel

from src.llms import select_streaming_llms
from src.models.context import ContextParty
from src.models.general import LLM, LLMSize


def _llm_model_id(model: BaseChatModel) -> str:
    """Stable model identifier across Gemini / OpenAI / Azure client classes."""
    for attr in ("model", "model_name", "deployment_name", "azure_deployment"):
        value = getattr(model, attr, None)
        if value:
            return str(value)
    return type(model).__name__


def llm_generation_fingerprint(
    llms: list[LLM],
    preferred_llm_size: LLMSize,
    use_premium_llms: bool,
) -> str:
    """Canonical snapshot of the roster ``stream_answer_from_llms`` would try."""
    candidates = select_streaming_llms(
        llms,
        preferred_llm_size=preferred_llm_size,
        use_premium_llms=use_premium_llms,
    )
    parts: list[str] = []
    for llm in candidates:
        model = llm.model
        parts.append(
            "|".join(
                [
                    llm.name,
                    _llm_model_id(model),
                    str(getattr(model, "temperature", "")),
                    str(getattr(model, "thinking_level", "")),
                    str(getattr(model, "thinking_budget", "")),
                ]
            )
        )
    return "\n".join(parts)


def build_answer_cache_key(
    *,
    question: str,
    conversation_history: str,
    system_prompt_template: str,
    user_prompt_template: str,
    party: ContextParty,
    context_id: str,
    answer_guidelines: str,
    rag_context: str,
    llm_size: LLMSize,
    use_premium_llms: bool,
    llms: list[LLM],
) -> str:
    """SHA-256 hex digest of the answer-LLM request (clock excluded).

    Always 64 lowercase hex characters — safe as a Firestore path segment.
    """
    payload = "\n".join(
        [
            f"q:{question}",
            f"hist:{conversation_history}",
            f"sys_tmpl:{system_prompt_template}",
            f"user_tmpl:{user_prompt_template}",
            (
                f"party:{party.party_id}|{party.name}|{party.long_name}|"
                f"{party.description or ''}|{party.candidate or ''}|"
                f"{party.website_url}"
            ),
            f"ctx:{context_id}",
            f"guidelines:{answer_guidelines}",
            f"rag:{rag_context}",
            f"llm_size:{llm_size.value}",
            f"premium:{use_premium_llms}",
            f"llm:{llm_generation_fingerprint(llms, llm_size, use_premium_llms)}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
