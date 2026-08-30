# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
User-requested source-type filter ("zeig mir nur Videos/Abstimmungen zu …").

Tests defined here:
  - _retrieve_party_buckets gating: only requested source legs run, requested
    legs get the raised _FILTERED_* budgets, "videos" adds the source=="op"
    provenance filter to the speech leg (unless "speeches" is also requested).
  - The default (no filter) path is byte-for-byte unchanged (all legs, original
    limits, no provenance filter).
  - A total failure of all REQUESTED sources raises RetrievalUnavailableError
    (the pre-filter literal 3 would let a votes-only outage stream ungrounded).
  - detect_source_filter is fail-open and returns canonical-order values.
  - _source_filter_note composition (empty / labels / video instruction).
  - generate_improvement_rag_query appends the topic-not-format note.
  - sources[] entries carry source_type.
  - the adaptive speech trim is skipped under a filter.

Behavioural tests — collaborators are monkeypatched; no LLM, no network, no
live Qdrant.
"""

import asyncio
import json
from datetime import datetime, timezone

import pytest

import src.chat_service as cs
import src.chatbot_async as ca
from src.chat_service import RetrievalUnavailableError, fetch_party_response_stream
from src.chatbot_async import (
    _source_filter_note,
    detect_source_filter,
    generate_improvement_rag_query,
    source_filter_labels_de,
)
from src.models.chat import GroupChatSession, Message
from src.models.context import ContextParty
from src.models.structured_outputs import SourceFilterClassifier

_TW = (
    datetime(2021, 1, 1, tzinfo=timezone.utc),
    datetime(2026, 1, 1, tzinfo=timezone.utc),
)


def _make_party(pid: str = "spd") -> ContextParty:
    return ContextParty(
        party_id=pid,
        name=pid.upper(),
        long_name=f"{pid.upper()} lang",
        website_url="https://example.com",
    )


def _make_session() -> GroupChatSession:
    return GroupChatSession(
        session_id="s1",
        context_id="c1",
        chat_history=[Message(id="m1", role="user", content="Frage?")],
    )


class _FakeEmbed:
    async def aembed_query(self, _query: str) -> list[float]:
        return [0.0, 0.1, 0.2]


def _drive_buckets(term_window, source_filter) -> None:
    asyncio.run(
        cs._retrieve_party_buckets(
            party=_make_party(),
            improved_rag_query="q",
            rag_query_vector=[0.0],
            region_path=["DE"],
            legislature_period_id=None,
            election_level="federal",
            term_window=term_window,
            manifesto_term_start=None,
            source_filter=source_filter,
        )
    )


def _recorder(store: dict, result):
    def _rec(_query, **kwargs):
        store[kwargs.get("source_type")] = kwargs
        return result

    return _rec


# ---------------------------------------------------------------------------
# Retrieval gating
# ---------------------------------------------------------------------------


def test_bucket_gating_votes_only(monkeypatch) -> None:
    """source_filter=["votes"] runs ONLY the vote leg (two-pass AND single-pass)
    with the raised filtered budget."""
    two_pass_calls: dict = {}
    monkeypatch.setattr(
        cs,
        "retrieve_two_pass",
        _recorder(two_pass_calls, {"current": [], "historic": []}),
    )
    _drive_buckets(_TW, ["votes"])
    assert set(two_pass_calls) == {"vote_record"}
    assert two_pass_calls["vote_record"]["current_limit"] == cs._FILTERED_VOTE_LIMIT

    single_calls: dict = {}
    monkeypatch.setattr(cs, "retrieve", _recorder(single_calls, []))
    _drive_buckets(None, ["votes"])
    assert set(single_calls) == {"vote_record"}
    assert single_calls["vote_record"]["limit"] == cs._FILTERED_VOTE_LIMIT


def test_bucket_gating_videos_only(monkeypatch) -> None:
    """source_filter=["videos"] runs ONLY the speech leg, with the Qdrant-level
    source=="op" provenance filter and the raised speech budget."""
    two_pass_calls: dict = {}
    monkeypatch.setattr(
        cs,
        "retrieve_two_pass",
        _recorder(two_pass_calls, {"current": [], "historic": []}),
    )
    _drive_buckets(_TW, ["videos"])
    assert set(two_pass_calls) == {"parliamentary_speech"}
    speech_kw = two_pass_calls["parliamentary_speech"]
    assert speech_kw["source"] == "op"
    assert speech_kw["current_limit"] == cs._FILTERED_SPEECH_LIMIT

    single_calls: dict = {}
    monkeypatch.setattr(cs, "retrieve", _recorder(single_calls, []))
    _drive_buckets(None, ["videos"])
    assert set(single_calls) == {"parliamentary_speech"}
    assert single_calls["parliamentary_speech"]["source"] == "op"


def test_bucket_gating_videos_plus_speeches_keeps_dip(monkeypatch) -> None:
    """ "speeches" alongside "videos" keeps the UNfiltered speech leg — the user
    asked for speeches in general, op results already rank first via dedup."""
    two_pass_calls: dict = {}
    monkeypatch.setattr(
        cs,
        "retrieve_two_pass",
        _recorder(two_pass_calls, {"current": [], "historic": []}),
    )
    _drive_buckets(_TW, ["speeches", "videos"])
    assert set(two_pass_calls) == {"parliamentary_speech"}
    assert two_pass_calls["parliamentary_speech"]["source"] is None


def test_bucket_default_all_sources_unchanged(monkeypatch) -> None:
    """No filter → all three legs with the original budgets and no provenance
    filter — the pre-feature behaviour, byte-for-byte."""
    two_pass_calls: dict = {}
    monkeypatch.setattr(
        cs,
        "retrieve_two_pass",
        _recorder(two_pass_calls, {"current": [], "historic": []}),
    )
    _drive_buckets(_TW, None)
    assert set(two_pass_calls) == {
        "vote_record",
        "party_manifesto",
        "parliamentary_speech",
    }
    assert two_pass_calls["vote_record"]["current_limit"] == cs._CURRENT_VOTE_LIMIT
    assert (
        two_pass_calls["party_manifesto"]["current_limit"]
        == cs._CURRENT_MANIFESTO_LIMIT
    )
    speech_kw = two_pass_calls["parliamentary_speech"]
    assert speech_kw["current_limit"] == cs._CURRENT_SPEECH_FALLBACK
    assert speech_kw["source"] is None


def test_requested_source_failure_fails_turn(monkeypatch) -> None:
    """When EVERY requested source fails, the turn must fail — with a votes-only
    filter a single vote-leg outage is a total outage (the pre-filter literal 3
    would stream an ungrounded 'successful' answer instead)."""

    def _boom(_query, **_kwargs):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(cs, "retrieve_two_pass", _boom)
    with pytest.raises(RetrievalUnavailableError):
        _drive_buckets(_TW, ["votes"])


def test_one_of_two_requested_sources_may_fail(monkeypatch) -> None:
    """With two requested sources, one failing leg degrades to empty buckets
    (per-source degradation) instead of failing the turn."""

    def _vote_fails(_query, **kwargs):
        if kwargs.get("source_type") == "vote_record":
            raise RuntimeError("vote leg down")
        return {"current": [], "historic": []}

    monkeypatch.setattr(cs, "retrieve_two_pass", _vote_fails)
    _drive_buckets(_TW, ["votes", "speeches"])  # must not raise


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------


def test_detect_source_filter_canonical_order_and_dedup(monkeypatch) -> None:
    async def _mock_structured(_llms, _messages, _model):
        return SourceFilterClassifier(
            requested_source_types=["videos", "votes", "votes"]
        )

    monkeypatch.setattr(ca, "get_structured_output_from_llms", _mock_structured)
    result = asyncio.run(detect_source_filter("msg", "history"))
    assert result == ["votes", "videos"]


def test_detect_source_filter_fail_open(monkeypatch) -> None:
    """A classifier error degrades to [] (all sources) — never a blocked turn."""

    async def _mock_structured(_llms, _messages, _model):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(ca, "get_structured_output_from_llms", _mock_structured)
    assert asyncio.run(detect_source_filter("msg", "history")) == []


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------


def test_source_filter_note_composition() -> None:
    assert _source_filter_note(None) == ""
    assert _source_filter_note([]) == ""

    votes_speeches = _source_filter_note(["votes", "speeches"])
    assert "namentliche Abstimmungen und Reden" in votes_speeches
    assert "Videoaufnahmen" not in votes_speeches

    videos = _source_filter_note(["videos"])
    assert "Videoaufnahmen von Reden" in videos
    # Video-specific instruction: never claim no video access; the citation
    # buttons open the recording.
    assert "NIEMALS" in videos
    assert "öffnen direkt die Videoaufnahme" in videos


def test_base_guidelines_describe_citation_rendering() -> None:
    """The shared Zitierstil block must tell the model its [N] citations render
    as clickable buttons — the model only sees its raw markdown and otherwise
    explains its own bracket syntax to users ('klicke auf die eckigen
    Klammern')."""
    from src.prompts import get_chat_answer_guidelines

    guidelines = get_chat_answer_guidelines("SPD")
    assert "klickbare Quellen-Buttons" in guidelines
    assert "Video-Button" in guidelines


def test_source_filter_labels_are_canonically_ordered() -> None:
    assert (
        source_filter_labels_de(["videos", "manifesto"])
        == "das Wahlprogramm und Videoaufnahmen von Reden"
    )


def test_improvement_query_gets_topic_not_format_note(monkeypatch) -> None:
    """With a filter active, the query-improvement system prompt instructs the
    model to query the TOPIC and never the media format; without a filter the
    prompt is unchanged."""
    captured: dict = {}

    class _Resp:
        content = "improved query"

    async def _mock_answer(_llms, messages):
        captured["system"] = messages[0].content
        return _Resp()

    monkeypatch.setattr(ca, "get_answer_from_llms", _mock_answer)

    asyncio.run(
        generate_improvement_rag_query(
            _make_party(),
            "conv",
            "Habt ihr Videos zum Lohnniveau?",
            source_filter=["videos"],
        )
    )
    assert "Quellenfokus des Nutzers" in captured["system"]
    assert "Videoaufnahmen von Reden" in captured["system"]

    asyncio.run(generate_improvement_rag_query(_make_party(), "conv", "Frage?"))
    assert "Quellenfokus des Nutzers" not in captured["system"]


# ---------------------------------------------------------------------------
# sources[] source_type marker + adaptive trim under filter
# ---------------------------------------------------------------------------


def _wire_stream_mocks(monkeypatch, capture: dict) -> None:
    async def _mock_rag_query(*_a, **_k) -> str:
        return "improved q"

    async def _mock_llm(_party, _conv, _question, combined_docs, **kwargs):
        capture["combined_docs"] = combined_docs
        capture["llm_kwargs"] = kwargs

        async def _gen():
            return
            yield  # pragma: no cover

        return _gen()

    monkeypatch.setattr(cs, "generate_improvement_rag_query", _mock_rag_query)
    monkeypatch.setattr(cs, "embed", _FakeEmbed())
    monkeypatch.setattr(cs, "generate_streaming_chatbot_response", _mock_llm)


def _drive_single_party(
    term_window, capture, monkeypatch, **stream_kwargs
) -> list[str]:
    _wire_stream_mocks(monkeypatch, capture)

    async def _run() -> list[str]:
        events: list[str] = []
        async for ev in fetch_party_response_stream(
            _make_party(),
            "conv",
            "q?",
            _make_session(),
            all_available_parties=[],
            is_cacheable_chat=False,
            region_path=["DE"],
            term_window=term_window,
            **stream_kwargs,
        ):
            events.append(ev)
        return events

    return asyncio.run(_run())


def _sources_from_events(events: list[str]) -> list[dict]:
    for ev in events:
        if '"sources_ready"' in ev:
            return json.loads(ev)["data"]["sources"]
    return []


def _manifesto_payload(title: str) -> dict:
    return {
        "citation_title": title,
        "citation_url": "https://example.com/m.pdf",
        "publish_date": "2025-01-01",
        "text": "manifesto text",
        "meta": {"page_start": 3},
    }


def _vote_payload(title: str) -> dict:
    return {
        "citation_title": title,
        "citation_url": "https://example.com/v",
        "publish_date": "2025-02-01",
        "region": "DE",
        "text": "vote text",
        "meta": {
            "motion_outcome": "angenommen",
            "vote_results": [
                {
                    "party_id": "spd",
                    "stance": "yes",
                    "yes": 100,
                    "no": 0,
                    "abstain": 0,
                    "no_show": 0,
                }
            ],
        },
    }


def _speech_payload(title: str) -> dict:
    return {
        "citation_title": title,
        "citation_url": "https://example.com/s.pdf",
        "publish_date": "2025-03-01",
        "source": "dip",
        "text": "speech text",
        "meta": {},
    }


def test_sources_carry_source_type(monkeypatch) -> None:
    """Every emitted sources[] entry names its corpus source category so the
    client can label/group by kind instead of sniffing URLs."""

    def _retrieve(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return [_manifesto_payload("Programm")]
        if st == "vote_record":
            return [_vote_payload("Abstimmung")]
        return [_speech_payload("Rede")]

    monkeypatch.setattr(cs, "retrieve", _retrieve)
    capture: dict = {}
    sources = _sources_from_events(_drive_single_party(None, capture, monkeypatch))

    by_name = {s["source"]: s for s in sources}
    assert by_name["Programm"]["source_type"] == "party_manifesto"
    assert by_name["Abstimmung"]["source_type"] == "vote_record"
    assert by_name["Rede"]["source_type"] == "parliamentary_speech"


def test_speech_trim_skipped_under_filter(monkeypatch) -> None:
    """With official data present the speech bucket is normally trimmed to
    _CURRENT_SPEECH_LIMIT; under a user filter the requested speeches keep their
    raised budget."""
    n_speeches = cs._CURRENT_SPEECH_LIMIT + 2

    def _retrieve(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return [_manifesto_payload("Programm")]
        if st == "vote_record":
            return [_vote_payload("Abstimmung")]
        return [_speech_payload(f"Rede {i}") for i in range(n_speeches)]

    def _speech_docs(docs) -> list:
        return [
            d for d in docs if d.metadata.get("source_type") == "parliamentary_speech"
        ]

    monkeypatch.setattr(cs, "retrieve", _retrieve)

    capture: dict = {}
    _drive_single_party(None, capture, monkeypatch)
    assert len(_speech_docs(capture["combined_docs"])) == cs._CURRENT_SPEECH_LIMIT

    capture_filtered: dict = {}
    _drive_single_party(
        None,
        capture_filtered,
        monkeypatch,
        source_filter=["manifesto", "votes", "speeches"],
    )
    assert len(_speech_docs(capture_filtered["combined_docs"])) == n_speeches
    # The filter must also reach answer generation for the prompt note.
    assert capture_filtered["llm_kwargs"]["source_filter"] == [
        "manifesto",
        "votes",
        "speeches",
    ]
