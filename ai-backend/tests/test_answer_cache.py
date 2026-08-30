# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Cache keys for the answer LLM request and the RAG rewrite request."""

from __future__ import annotations

import re

from langchain_core.documents import Document

from src.answer_cache import (
    build_answer_cache_key,
    build_rag_query_cache_key,
    canonicalize_rag_context,
    llm_generation_fingerprint,
    llm_invoke_fingerprint,
)
from src.llms import (
    PRE_AND_POST_PROCESSING_LLMS,
    RESPONSE_GENERATION_LLMS,
    select_streaming_llms,
)
from src.prompts import (
    party_response_system_prompt_template_str,
    streaming_party_response_user_prompt_template_str,
    system_prompt_improvement_template_str,
    user_prompt_improvement_template_str,
)
from src.models.context import ContextParty

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
        llms=RESPONSE_GENERATION_LLMS,
    )
    kwargs.update(overrides)
    return kwargs


def test_clock_is_not_a_key_input() -> None:
    """Date and time must not be key fields."""
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


def test_key_encoding_is_injective_across_newlines() -> None:
    """A newline and a field name inside one value must not match two fields."""
    a = build_answer_cache_key(
        **_key_kwargs(question="foo\nhist:bar", conversation_history="")
    )
    b = build_answer_cache_key(
        **_key_kwargs(question="foo", conversation_history="bar")
    )
    assert a != b


def test_party_field_separator_is_injective() -> None:
    """A pipe in a party field must not match a split across two fields."""
    a = build_answer_cache_key(
        **_key_kwargs(party=_party(name="SPD", long_name="eins"))
    )
    b = build_answer_cache_key(
        **_key_kwargs(party=_party(name="SPD|eins", long_name=""))
    )
    assert a != b


def test_wahl_chat_prompt_variables_change_key() -> None:
    """A change to context name, date text, location, or party list must miss."""
    base = _key_kwargs(
        context_id="bundestagswahl-2025",
        context_name="Bundestagswahl 2025",
        context_date_info="Findet statt am 23. Februar 2025",
        context_location="Deutschland",
        all_parties_list="### SPD\n",
    )
    assert build_answer_cache_key(**base) != build_answer_cache_key(
        **{**base, "context_name": "Bundestagswahl 2029"}
    )
    assert build_answer_cache_key(**base) != build_answer_cache_key(
        **{**base, "context_date_info": "Hat stattgefunden am 23. Februar 2025"}
    )
    assert build_answer_cache_key(**base) != build_answer_cache_key(
        **{**base, "context_location": "Berlin"}
    )
    assert build_answer_cache_key(**base) != build_answer_cache_key(
        **{**base, "all_parties_list": "### SPD\n### CDU\n"}
    )


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
    """The same sources in a different order must produce the same key."""
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
    """A new source must change the canonical context."""
    previous = [_chunk("prog", "Klimaschutz")]
    with_new = previous + [
        _chunk("abstimmung", "Ja-Stimmen", source_type="vote_record")
    ]
    assert canonicalize_rag_context(previous) != canonicalize_rag_context(with_new)


def test_canonical_rag_context_includes_url_and_page() -> None:
    """A URL or page change must miss even if the text is the same."""
    base = [_chunk("prog", "Klimaschutz")]
    new_url = [
        Document(
            page_content="Klimaschutz",
            metadata={
                **base[0].metadata,
                "url": "https://example.com/prog#updated",
            },
        )
    ]
    new_page = [
        Document(
            page_content="Klimaschutz",
            metadata={**base[0].metadata, "page": 2},
        )
    ]
    assert canonicalize_rag_context(base) != canonicalize_rag_context(new_url)
    assert canonicalize_rag_context(base) != canonicalize_rag_context(new_page)
    assert build_answer_cache_key(
        **_key_kwargs(rag_context=canonicalize_rag_context(base))
    ) != build_answer_cache_key(
        **_key_kwargs(rag_context=canonicalize_rag_context(new_url))
    )


def test_guidelines_change_key() -> None:
    a = build_answer_cache_key(**_key_kwargs(answer_guidelines="A"))
    b = build_answer_cache_key(**_key_kwargs(answer_guidelines="B"))
    assert a != b


def test_llm_roster_changes_key() -> None:
    """A shorter model list must change the key."""
    full = build_answer_cache_key(**_key_kwargs(llms=RESPONSE_GENERATION_LLMS))
    truncated = build_answer_cache_key(**_key_kwargs(llms=RESPONSE_GENERATION_LLMS[1:]))
    assert full != truncated


def test_fingerprint_tracks_select_streaming_llms() -> None:
    """The fingerprint must follow the streamer roster order."""
    fp = llm_generation_fingerprint(RESPONSE_GENERATION_LLMS)
    selected = select_streaming_llms(RESPONSE_GENERATION_LLMS)
    assert fp.split("\n")[0].startswith(selected[0].name)
    assert selected == sorted(
        RESPONSE_GENERATION_LLMS, key=lambda llm: llm.priority, reverse=True
    )


def test_select_streaming_llms_orders_by_priority() -> None:
    selected = select_streaming_llms(RESPONSE_GENERATION_LLMS)
    priorities = [llm.priority for llm in selected]
    assert priorities == sorted(priorities, reverse=True)


def _rag_key_kwargs(**overrides: object) -> dict:
    kwargs: dict = dict(
        question="Was ist eure Klimapolitik?",
        conversation_history="",
        system_prompt_template=system_prompt_improvement_template_str,
        user_prompt_template=user_prompt_improvement_template_str,
        party=_party(),
        context_id="bundestagswahl-2025",
        source_filter=None,
        llms=PRE_AND_POST_PROCESSING_LLMS,
    )
    kwargs.update(overrides)
    return kwargs


def test_rag_query_key_is_sha256_hex() -> None:
    assert _SHA256_HEX.fullmatch(build_rag_query_cache_key(**_rag_key_kwargs()))


def test_rag_query_key_question_changes() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(question="A"))
    b = build_rag_query_cache_key(**_rag_key_kwargs(question="B"))
    assert a != b


def test_rag_query_key_encoding_is_injective_across_newlines() -> None:
    a = build_rag_query_cache_key(
        **_rag_key_kwargs(question="foo\nhist:bar", conversation_history="")
    )
    b = build_rag_query_cache_key(
        **_rag_key_kwargs(question="foo", conversation_history="bar")
    )
    assert a != b


def test_rag_query_key_history_changes() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(conversation_history=""))
    b = build_rag_query_cache_key(
        **_rag_key_kwargs(conversation_history='1. Nutzer: "Vorher"\n')
    )
    assert a != b


def test_rag_query_key_context_changes() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(context_id="bundestagswahl-2025"))
    b = build_rag_query_cache_key(
        **_rag_key_kwargs(context_id="landtagswahl-baden-wuerttemberg-2026")
    )
    assert a != b


def test_rag_query_key_party_name_changes() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(party=_party(name="SPD")))
    b = build_rag_query_cache_key(**_rag_key_kwargs(party=_party(name="CDU")))
    assert a != b


def test_rag_query_key_none_and_empty_filter_collide() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(source_filter=None))
    b = build_rag_query_cache_key(**_rag_key_kwargs(source_filter=[]))
    assert a == b


def test_rag_query_key_filter_changes() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(source_filter=None))
    b = build_rag_query_cache_key(**_rag_key_kwargs(source_filter=["videos"]))
    assert a != b


def test_rag_query_key_filter_order_independent() -> None:
    a = build_rag_query_cache_key(
        **_rag_key_kwargs(source_filter=["videos", "manifesto"])
    )
    b = build_rag_query_cache_key(
        **_rag_key_kwargs(source_filter=["manifesto", "videos"])
    )
    assert a == b


def test_rag_query_key_prompt_template_changes() -> None:
    a = build_rag_query_cache_key(**_rag_key_kwargs(system_prompt_template="SYS-A"))
    b = build_rag_query_cache_key(**_rag_key_kwargs(system_prompt_template="SYS-B"))
    assert a != b


def test_rag_query_key_roster_changes() -> None:
    full = build_rag_query_cache_key(
        **_rag_key_kwargs(llms=PRE_AND_POST_PROCESSING_LLMS)
    )
    truncated = build_rag_query_cache_key(
        **_rag_key_kwargs(llms=PRE_AND_POST_PROCESSING_LLMS[1:])
    )
    assert full != truncated


def test_invoke_fingerprint_follows_get_answer_priority() -> None:
    """The first line is the highest-priority primary model."""
    fp = llm_invoke_fingerprint(PRE_AND_POST_PROCESSING_LLMS)
    ordered = sorted(
        PRE_AND_POST_PROCESSING_LLMS, key=lambda llm: llm.priority, reverse=True
    )
    primaries = [llm for llm in ordered if not llm.back_up_only]
    assert fp.split("\n")[0].startswith(primaries[0].name)
