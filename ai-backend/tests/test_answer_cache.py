# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Exact-match answer-cache key: every answer-LLM input except the clock."""

from __future__ import annotations

import re

from langchain_core.documents import Document

from src.answer_cache import (
    build_answer_cache_key,
    canonicalize_rag_context,
    llm_generation_fingerprint,
)
from src.llms import RESPONSE_GENERATION_LLMS, select_streaming_llms
from src.models.context import ContextParty
from src.models.general import LLMSize
from src.prompts import (
    party_response_system_prompt_template_str,
    streaming_party_response_user_prompt_template_str,
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _party(**overrides: object) -> ContextParty:
    fields = dict(
        party_id="spd",
        name="SPD",
        long_name="Sozialdemokratische Partei Deutschlands",
        website_url="https://www.spd.de",
        description="Beschreibung",
        candidate="Kandidat",
    )
    fields.update(overrides)
    return ContextParty(**fields)  # type: ignore[arg-type]


def _key_kwargs(**overrides: object) -> dict:
    kwargs: dict = dict(
        question="Was ist eure Klimapolitik?",
        conversation_history="",
        system_prompt_template=party_response_system_prompt_template_str,
        user_prompt_template=streaming_party_response_user_prompt_template_str,
        party=_party(),
        context_id="bundestagswahl-2025",
        answer_guidelines="Leitlinien",
        rag_context="RAG-Kontext",
        llm_size=LLMSize.LARGE,
        use_premium_llms=False,
        llms=RESPONSE_GENERATION_LLMS,
    )
    kwargs.update(overrides)
    return kwargs


def test_clock_is_not_a_key_input() -> None:
    """The live system prompt injects date/time; those must not be key fields."""
    import inspect

    params = inspect.signature(build_answer_cache_key).parameters
    assert "date" not in params
    assert "time" not in params


def test_key_is_sha256_hex() -> None:
    key = build_answer_cache_key(**_key_kwargs())
    assert _SHA256_HEX.fullmatch(key)


def test_question_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(question="A"))
    b = build_answer_cache_key(**_key_kwargs(question="B"))
    assert a != b


def test_history_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(conversation_history=""))
    b = build_answer_cache_key(
        **_key_kwargs(conversation_history='1. Nutzer: "Vorher"\n')
    )
    assert a != b


def test_system_prompt_template_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(system_prompt_template="SYS-A"))
    b = build_answer_cache_key(**_key_kwargs(system_prompt_template="SYS-B"))
    assert a != b


def test_party_description_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(party=_party(description="eins")))
    b = build_answer_cache_key(**_key_kwargs(party=_party(description="zwei")))
    assert a != b


def test_context_id_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(context_id="bundestagswahl-2025"))
    b = build_answer_cache_key(
        **_key_kwargs(context_id="landtagswahl-baden-wuerttemberg-2026")
    )
    assert a != b


def test_rag_context_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(rag_context="chunk-1"))
    b = build_answer_cache_key(**_key_kwargs(rag_context="chunk-2"))
    assert a != b


def _chunk(
    name: str, content: str, *, source_type: str = "party_manifesto"
) -> Document:
    return Document(
        page_content=content,
        metadata={
            "document_name": name,
            "document_publish_date": "2025-01-01",
            "authority_tier": "authoritative",
            "source_type": source_type,
            "url": f"https://example.com/{name}",
            "page": 1,
        },
    )


def test_canonical_rag_context_is_order_independent() -> None:
    """Same sources in a different retrieval rank must produce the same key."""
    a = [
        _chunk("prog", "Klimaschutz"),
        _chunk("rede", "In der Rede", source_type="parliamentary_speech"),
    ]
    b = list(reversed(a))
    assert canonicalize_rag_context(a) == canonicalize_rag_context(b)
    assert build_answer_cache_key(
        **_key_kwargs(rag_context=canonicalize_rag_context(a))
    ) == build_answer_cache_key(**_key_kwargs(rag_context=canonicalize_rag_context(b)))


def test_new_rag_source_changes_canonical_context() -> None:
    """A newly ingested chunk must miss the cache so the answer is regenerated."""
    previous = [_chunk("prog", "Klimaschutz")]
    with_new = previous + [
        _chunk("abstimmung", "Ja-Stimmen", source_type="vote_record")
    ]
    assert canonicalize_rag_context(previous) != canonicalize_rag_context(with_new)


def test_guidelines_change_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(answer_guidelines="A"))
    b = build_answer_cache_key(**_key_kwargs(answer_guidelines="B"))
    assert a != b


def test_premium_flag_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(use_premium_llms=False))
    b = build_answer_cache_key(**_key_kwargs(use_premium_llms=True))
    assert a != b


def test_llm_size_changes_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(llm_size=LLMSize.LARGE))
    b = build_answer_cache_key(**_key_kwargs(llm_size=LLMSize.SMALL))
    assert a != b


def test_llm_roster_changes_key() -> None:
    """Dropping a candidate (model swap / different temperature roster) busts the key."""
    full = build_answer_cache_key(**_key_kwargs(llms=RESPONSE_GENERATION_LLMS))
    truncated = build_answer_cache_key(**_key_kwargs(llms=RESPONSE_GENERATION_LLMS[1:]))
    assert full != truncated


def test_fingerprint_tracks_select_streaming_llms() -> None:
    """Fingerprint walks the same ordered roster the streamer will try."""
    fp = llm_generation_fingerprint(
        RESPONSE_GENERATION_LLMS, LLMSize.LARGE, use_premium_llms=False
    )
    selected = select_streaming_llms(
        RESPONSE_GENERATION_LLMS,
        preferred_llm_size=LLMSize.LARGE,
        use_premium_llms=False,
    )
    assert fp.split("\n")[0].startswith(selected[0].name)
    for llm in selected:
        assert llm.premium_only is False


def test_select_streaming_llms_rejects_invalid_size() -> None:
    try:
        select_streaming_llms(RESPONSE_GENERATION_LLMS, preferred_llm_size="tiny")  # type: ignore[arg-type]
    except ValueError as exc:
        assert "Invalid preferred LLM size" in str(exc)
    else:
        raise AssertionError("expected ValueError")
