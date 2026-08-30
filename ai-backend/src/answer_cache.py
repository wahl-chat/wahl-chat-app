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

    Citation URL and page are hashed in addition to the excerpt the LLM
    sees: a link or page-anchor change must miss even when the text is
    unchanged, so a cached answer cannot keep pointing at a stale source.
    """
    ordered = sorted(docs, key=_rag_doc_sort_key)
    citations: list[str] = []
    for doc in ordered:
        meta = doc.metadata or {}
        page = meta.get("page")
        citations.append(f"{meta.get('url') or ''}\t{'' if page is None else page}")
    return get_rag_context(ordered) + "\n\x1e\n" + "\n".join(citations)


def _digest_fields(fields: list[tuple[str, str]]) -> str:
    """SHA-256 of length-prefixed name/value pairs.

    Joining with newlines is not injective: a value can contain ``\\n`` and
    a prefix like ``hist:``, so two different requests can share a payload.
    Framing each value by its UTF-8 byte length makes the encoding injective
    regardless of what the fields contain.
    """
    buf = bytearray()
    for name, value in fields:
        encoded = value.encode("utf-8")
        buf.extend(f"{name}:{len(encoded)}:".encode("ascii"))
        buf.extend(encoded)
    return hashlib.sha256(buf).hexdigest()


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
    context_name: str = "",
    context_date_info: str = "",
    context_location: str = "",
    all_parties_list: str = "",
) -> str:
    """SHA-256 hex digest of the answer-LLM request (clock excluded).

    ``rag_context`` must already be the canonical (order-independent)
    serialization from ``canonicalize_rag_context`` — included so newly
    ingested sources miss the cache and get a fresh answer.

    The wahl.chat system prompt also injects ``context_name`` /
    ``context_date_info`` / ``context_location`` / ``all_parties_list``.
    Those are hashed here so a renamed election, moved date, or updated
    party roster misses even when ``context_id`` is unchanged. The request
    clock (``{date}`` / ``{time}``) stays out.

    Always 64 lowercase hex characters — safe as a Firestore path segment.
    """
    return _digest_fields(
        [
            ("q", question),
            ("hist", conversation_history),
            ("sys_tmpl", system_prompt_template),
            ("user_tmpl", user_prompt_template),
            ("party_id", party.party_id),
            ("party_name", party.name),
            ("party_long", party.long_name),
            ("party_desc", party.description or ""),
            ("party_cand", party.candidate or ""),
            ("party_url", party.website_url),
            ("ctx", context_id),
            ("ctx_name", context_name),
            ("ctx_date", context_date_info),
            ("ctx_loc", context_location),
            ("parties", all_parties_list),
            ("guidelines", answer_guidelines),
            ("rag", rag_context),
            ("llm_size", llm_size.value),
            ("premium", str(use_premium_llms)),
            (
                "llm",
                llm_generation_fingerprint(llms, llm_size, use_premium_llms),
            ),
        ]
    )


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
    return _digest_fields(
        [
            ("q", question),
            ("hist", conversation_history),
            ("sys_tmpl", system_prompt_template),
            ("user_tmpl", user_prompt_template),
            ("party_id", party.party_id),
            ("party_name", party.name),
            ("ctx", context_id),
            ("filter", ",".join(sorted(source_filter or []))),
            ("llm", llm_invoke_fingerprint(llms)),
        ]
    )
