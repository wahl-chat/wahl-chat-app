# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Cache keys for proposed-question answers and RAG query rewrites.

The answer key includes every input to the answer LLM except the clock.
Retrieved chunks are in the key, so a new source causes a miss. Chunk
order does not matter. The rewrite has its own key so a repeat uses the
same query.
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
    """Models ``stream_answer_from_llms`` will try, in order."""
    candidates = select_streaming_llms(
        llms,
        preferred_llm_size=preferred_llm_size,
        use_premium_llms=use_premium_llms,
    )
    return "\n".join(_llm_line(llm) for llm in candidates)


def llm_invoke_fingerprint(llms: list[LLM]) -> str:
    """Models ``get_answer_from_llms`` will try, in priority order.

    Includes backup models. A model or temperature change must change the key.
    """
    ordered = sorted(llms, key=lambda llm: llm.priority, reverse=True)
    primaries = [llm for llm in ordered if not llm.back_up_only]
    backups = [llm for llm in ordered if llm.back_up_only]
    return "\n".join(_llm_line(llm) for llm in primaries + backups)


def _rag_doc_sort_key(doc: Document) -> tuple[str, ...]:
    """Identity of one chunk. Used to sort, not to rank."""
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
    """Serialize chunks so order does not change the string.

    Include URL and page. A link or page change must miss even if the
    text is the same.
    """
    ordered = sorted(docs, key=_rag_doc_sort_key)
    citations: list[str] = []
    for doc in ordered:
        meta = doc.metadata or {}
        page = meta.get("page")
        citations.append(f"{meta.get('url') or ''}\t{'' if page is None else page}")
    return get_rag_context(ordered) + "\n\x1e\n" + "\n".join(citations)


def _digest_fields(fields: list[tuple[str, str]]) -> str:
    """SHA-256 of name/value pairs. Each value is prefixed with its byte length.

    A newline join is not safe: a value can contain a newline and look like
    another field.
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
    """SHA-256 of the answer LLM request. Date and time are not included.

    ``rag_context`` must come from ``canonicalize_rag_context``.
    wahl.chat also hashes context name, date text, location, and the party
    list. The result is 64 lowercase hex characters.
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
    """SHA-256 of the RAG rewrite request.

    ``None`` and ``[]`` source filters share a key.
    The result is 64 lowercase hex characters.
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
