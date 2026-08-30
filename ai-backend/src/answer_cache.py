# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Exact-match cache keys for curated (proposed-question) party answers.

A cached answer is replayed only when every input to the answer LLM matches:
question, preceding conversation, prompt templates and stable variables,
retrieved RAG context, and the generation roster (model, temperature, …).
The clock injected into the live system prompt (``{date}`` / ``{time}``) is
deliberately omitted so two otherwise-identical requests a minute apart can
still hit.

Retrieved chunks are part of the answer key so a later ingestion — a new
manifesto page, vote, or speech — produces a different key and a freshly
generated answer, rather than replaying one grounded on a stale corpus
snapshot. Chunk *order* is canonicalized (sorted by stable document
identity) so a retrieval-rank reshuffle of the same set still hits.

The RAG rewrite that *produces* those chunks is a separate LLM call and
has its own key (``build_rag_query_cache_key``). Caching that rewrite
keeps the retrieval query — and therefore the answer-key ``rag_context``
— stable across otherwise-identical curated turns, and skips the rewrite
cost on a hit.
"""

from __future__ import annotations

import hashlib

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from src.chatbot_async import get_rag_context
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


def _llm_line(llm: LLM) -> str:
    model = llm.model
    return "|".join(
        [
            llm.name,
            _llm_model_id(model),
            str(getattr(model, "temperature", "")),
            str(getattr(model, "thinking_level", "")),
            str(getattr(model, "thinking_budget", "")),
        ]
    )


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
    return "\n".join(_llm_line(llm) for llm in candidates)


def llm_invoke_fingerprint(llms: list[LLM]) -> str:
    """Canonical snapshot of the roster ``get_answer_from_llms`` would try.

    That helper has no size/premium filter: it walks every model by priority,
    primaries first, then ``back_up_only``. A model swap or temperature change
    on any candidate therefore invalidates the RAG-query cache.
    """
    ordered = sorted(llms, key=lambda llm: llm.priority, reverse=True)
    primaries = [llm for llm in ordered if not llm.back_up_only]
    backups = [llm for llm in ordered if llm.back_up_only]
    return "\n".join(_llm_line(llm) for llm in primaries + backups)


def _rag_doc_sort_key(doc: Document) -> tuple[str, ...]:
    """Stable identity for one retrieved chunk — not retrieval rank."""
    meta = doc.metadata or {}
    page = meta.get("page")
    return (
        str(meta.get("source_type") or ""),
        str(meta.get("document_name") or ""),
        str(meta.get("document_publish_date") or ""),
        "" if page is None else str(page),
        str(meta.get("url") or ""),
        str(meta.get("authority_tier") or ""),
        doc.page_content,
    )


def canonicalize_rag_context(docs: list[Document]) -> str:
    """Serialize retrieved chunks in a retrieval-order-independent form.

    Same set of sources → same string, even if HNSW returned them in a
    different rank order. A new or dropped source changes the set and
    therefore the cache key, so the next user gets a freshly generated
    answer grounded on the updated corpus.
    """
    return get_rag_context(sorted(docs, key=_rag_doc_sort_key))


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

    ``rag_context`` must already be the canonical (order-independent)
    serialization from ``canonicalize_rag_context`` — included so newly
    ingested sources miss the cache and get a fresh answer.

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


def build_rag_query_cache_key(
    *,
    question: str,
    conversation_history: str,
    system_prompt_template: str,
    user_prompt_template: str,
    party: ContextParty,
    context_id: str,
    source_filter: list[str] | None,
    llms: list[LLM],
) -> str:
    """SHA-256 hex digest of the RAG-rewrite LLM request.

    The rewrite is itself an LLM call: without this key the same curated
    question can emit a different query string, retrieve a different chunk
    set, and miss the answer cache. Caching the rewrite keeps retrieval
    input stable (corpus changes still bust the answer key via
    ``rag_context``) and skips the rewrite cost on a hit.

    ``source_filter`` is canonicalized so ``None`` and ``[]`` collide.
    Always 64 lowercase hex characters — safe as a Firestore path segment.
    """
    payload = "\n".join(
        [
            f"q:{question}",
            f"hist:{conversation_history}",
            f"sys_tmpl:{system_prompt_template}",
            f"user_tmpl:{user_prompt_template}",
            f"party:{party.party_id}|{party.name}",
            f"ctx:{context_id}",
            f"filter:{','.join(sorted(source_filter or []))}",
            f"llm:{llm_invoke_fingerprint(llms)}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
