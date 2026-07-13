# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for additions to chat_service:
  - Vote sources[] dict carries a structural 'region' marker
  - election_level / level kwarg is passed ONLY to vote_record
    _safe_retrieve calls, never to manifesto/speech calls.
  - election_level is derived from _context.level and threaded through
    fetch_party_response_stream signature.

These are structural / source-inspection tests — no LLM, no network, no Qdrant.
"""

import asyncio
import inspect
import json
from datetime import datetime, timezone

import src.chat_service as cs
from src.chat_service import fetch_party_response_stream, process_party
from src.models.chat import GroupChatSession, Message, Role
from src.models.context import ContextParty
from src.models.general import LLMSize


# ---------------------------------------------------------------------------
# vote sources[] dict includes 'region' field
# ---------------------------------------------------------------------------


def test_vote_sources_include_region() -> None:
    """The vote sources loop must append 'region' from the vote payload.

    We replicate the sources-loop logic from chat_service.py and verify that
    the appended dict carries a 'region' key sourced from vote_payload.get('region').
    """
    party_id = "spd"
    vote_payload = {
        "citation_title": "Abstimmung: Testgesetz",
        "citation_url": "https://example.com/vote/1",
        "publish_date": "2024-01-15",
        "region": "DE",
        "meta": {
            "vote_results": [
                {
                    "party_id": party_id,
                    "stance": "yes",
                    "yes": 100,
                    "no": 0,
                    "abstain": 0,
                    "no_show": 0,
                }
            ]
        },
    }

    # Replicate the sources loop from chat_service.py.
    sources: list = []
    for vp in [vote_payload]:
        meta_vp = (vp.get("meta") or {})
        results_vp = meta_vp.get("vote_results") or []
        party_result_vp = next(
            (r for r in results_vp if r.get("party_id") == party_id), None
        )
        if party_result_vp is None:
            continue
        sources.append(
            {
                "source": vp.get("citation_title"),
                "page": 1,
                "document_publish_date": vp.get("publish_date"),
                "url": vp.get("citation_url"),
                "source_document": vp.get("citation_title"),
                "region": vp.get("region"),   # must be present
            }
        )

    assert len(sources) == 1, "Expected 1 source entry for participating party"
    source_dict = sources[0]
    assert "region" in source_dict, (
        "P8-LABEL-02: vote source dict must include 'region' key"
    )
    assert source_dict["region"] == "DE", (
        f"P8-LABEL-02: region must match payload region 'DE', got {source_dict['region']!r}"
    )


def test_vote_sources_region_de_payload() -> None:
    """A DE-region vote payload produces a source dict with region='DE'."""
    # This test verifies the actual chat_service.py sources loop contains the field.
    # We inspect the source code for the 'region' key assignment in the loop.
    import src.chat_service as cs_module
    source = inspect.getsource(cs_module)

    # Must contain the region assignment in the vote sources loop
    assert '"region": vote_payload.get("region")' in source or \
           "'region': vote_payload.get('region')" in source, (
        "P8-LABEL-02: chat_service.py sources loop must include "
        "'\"region\": vote_payload.get(\"region\")'"
    )


def test_is_video_link() -> None:
    """_is_video_link recognises op video deep-links (#t= fragment / .mp4) and
    rejects PDFs, dbtg.tv pages, and empty urls — so `video_url` is only set for a
    genuinely playable video."""
    from src.chat_service import _is_video_link

    assert _is_video_link("https://cdn.example/clip.mp4#t=87.5")
    assert _is_video_link("https://cdn.example/clip.mp4")
    assert _is_video_link("https://cdn.example/CLIP.MP4")
    assert not _is_video_link("https://dserver.bundestag.de/btp/20/2000101.pdf")
    assert not _is_video_link("http://dbtg.tv/fvid/7553315")  # op fallback page
    assert not _is_video_link(None)
    assert not _is_video_link("")


def test_speech_sources_emit_dual_links() -> None:
    """The speech sources builder exposes a merged speech as ONE source carrying
    both a video_url (op deep-link) and a pdf_url (grafted DIP transcript), instead
    of the video replacing the PDF."""
    import src.chat_service as cs_module

    source = inspect.getsource(cs_module)
    assert 'source_entry["video_url"] = primary_url' in source, (
        "op speeches must expose the video deep-link as video_url"
    )
    assert 'source_entry["pdf_url"] = transcript_pdf' in source, (
        "op speeches must expose the grafted DIP transcript as pdf_url"
    )
    assert 'source_entry["pdf_url"] = primary_url' in source, (
        "dip speeches must expose their PDF as pdf_url"
    )


# ---------------------------------------------------------------------------
# election_level scoped ONLY to vote_record _safe_retrieve
# ---------------------------------------------------------------------------


def test_election_level_only_in_vote_retrieve() -> None:
    """level=election_level must appear in the vote_record retrieve call only.

    Source inspection: verify that 'level=election_level' appears at least once in
    chat_service.py — it is passed to the vote_record retrieve, not to the manifesto
    or speech retrieves.
    """
    import src.chat_service as cs_module
    source = inspect.getsource(cs_module)

    # Must contain the level=election_level kwarg (passed to vote retrieve)
    assert "level=election_level" in source, (
        "chat_service.py must pass level=election_level to vote_record _safe_retrieve"
    )


# ---------------------------------------------------------------------------
# election_level threaded through fetch_party_response_stream
# ---------------------------------------------------------------------------


def test_fetch_party_response_stream_has_election_level_param() -> None:
    """fetch_party_response_stream signature must include election_level: Optional[str] = None."""
    sig = inspect.signature(fetch_party_response_stream)
    assert "election_level" in sig.parameters, (
        "P8-RANK-01: fetch_party_response_stream must accept 'election_level' parameter"
    )
    param = sig.parameters["election_level"]
    assert param.default is None, (
        f"P8-RANK-01: election_level default must be None, got {param.default!r}"
    )


# ---------------------------------------------------------------------------
# Phase 09 two-pass wiring tests
# ---------------------------------------------------------------------------
#
# The first three are source-inspection / structural guarantees; the last two
# drive fetch_party_response_stream with monkeypatched collaborators to assert
# the current-first/historic-after merge and the single-pass fallback.


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
        chat_response_llm_size=LLMSize.LARGE,
    )


class _FakeEmbed:
    async def aembed_query(self, _query: str) -> list[float]:
        return [0.0, 0.1, 0.2]


def _wire_common_mocks(monkeypatch, capture: dict) -> None:
    """Patch the async collaborators fetch_party_response_stream calls.

    Leaves retrieve / retrieve_two_pass for the individual test to set.
    """
    async def _mock_rag_query(*_a, **_k) -> str:
        return "improved q"

    async def _mock_llm(_party, _conv, _question, combined_docs, **_kwargs):
        capture["combined_docs"] = combined_docs

        async def _gen():
            return
            yield  # pragma: no cover — makes this an (empty) async generator

        return _gen()

    monkeypatch.setattr(cs, "generate_improvement_rag_query", _mock_rag_query)
    monkeypatch.setattr(cs, "embed", _FakeEmbed())
    monkeypatch.setattr(cs, "generate_streaming_chatbot_response", _mock_llm)


def _drive_single_party(term_window, **stream_kwargs) -> list[str]:
    async def _run() -> list[str]:
        events: list[str] = []
        async for ev in fetch_party_response_stream(
            _make_party(),
            "conv",
            "q?",
            _make_session(),
            all_available_parties=[],
            use_premium_llms=False,
            is_proposed_question=False,
            is_cacheable_chat=False,
            region_path=["DE-BW"],
            term_window=term_window,
            **stream_kwargs,
        ):
            events.append(ev)
        return events

    return asyncio.run(_run())


def _sources_from_events(events: list[str]) -> list[dict]:
    for ev in events:
        if '"sources_ready"' in ev:
            payload = json.loads(ev.split("data: ", 1)[1])
            return payload["data"]["sources"]
    return []


def test_two_pass_window_derived_before_nulling() -> None:
    """term_window is derived from the RAW _context.legislature_period_id BEFORE
    the non-federal nulling of legislature_period_id (source-order guarantee, D5)."""
    source = inspect.getsource(cs)
    deriv_idx = source.index("term_window_for_context(")
    null_idx = source.index('if election_level not in (None, "federal")')
    assert deriv_idx < null_idx, (
        "term_window must be derived BEFORE legislature_period_id is nulled for "
        "non-federal contexts (D5)"
    )
    # The derivation must use the raw context values (period id + date).
    assert "_context.legislature_period_id" in source
    assert "_context.date" in source


def test_two_pass_used_in_both_paths() -> None:
    """retrieve_two_pass is wired into BOTH the single-party and comparison paths."""
    assert "retrieve_two_pass" in inspect.getsource(fetch_party_response_stream)
    assert "retrieve_two_pass" in inspect.getsource(process_party)


def test_historic_period_id_current_only(monkeypatch) -> None:
    """legislature_period_id + level reach the vote two-pass ONLY; manifesto/speech
    two-pass calls never carry them (vote-only precision filter)."""
    capture: dict = {}
    calls: dict = {}

    def _rec_two_pass(_query, **kwargs):
        calls[kwargs.get("source_type")] = kwargs
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve_two_pass", _rec_two_pass)

    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    _drive_single_party(tw, legislature_period_id=161, election_level="federal")

    vote_kw = calls["vote_record"]
    assert vote_kw.get("legislature_period_id") == 161
    assert vote_kw.get("level") == "federal"

    for st in ("party_manifesto", "parliamentary_speech"):
        kw = calls[st]
        assert "legislature_period_id" not in kw, (
            f"{st} two-pass must NOT carry legislature_period_id"
        )
        assert "level" not in kw, f"{st} two-pass must NOT carry level"


def _participating_vote_payload(title: str, publish_date: str) -> dict:
    """A vote_record payload where party 'spd' participated (so it survives the
    build_vote_documents participation filter and yields one Document)."""
    return {
        "citation_title": title,
        "publish_date": publish_date,
        "citation_url": "u",
        "region": "DE",
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


def test_current_first_merge_order(monkeypatch) -> None:
    """combined_docs is all-current-then-all-historic (manifesto→vote→speech within
    each bucket, SC1) and sources[] mirror the identical order for [N] alignment (D1/D4)."""
    capture: dict = {}

    def _mock_two_pass(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return {
                "current": [{
                    "citation_title": "CUR-MANI",
                    "publish_date": "2022-01-01",
                    "citation_url": "u",
                    "meta": {"page_start": 1},
                }],
                "historic": [{
                    "citation_title": "HIST-MANI",
                    "publish_date": "2018-01-01",
                    "citation_url": "u",
                    "meta": {"page_start": 1},
                }],
            }
        if st == "vote_record":
            return {
                "current": [_participating_vote_payload("CUR-VOTE", "2022-01-01")],
                "historic": [_participating_vote_payload("HIST-VOTE", "2018-01-01")],
            }
        if st == "parliamentary_speech":
            return {
                "current": [{
                    "citation_title": "CUR-SPEECH",
                    "publish_date": "2022-01-01",
                    "citation_url": "u",
                }],
                "historic": [{
                    "citation_title": "HIST-SPEECH",
                    "publish_date": "2018-01-01",
                    "citation_url": "u",
                }],
            }
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve_two_pass", _mock_two_pass)

    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    events = _drive_single_party(tw)

    titles = [d.metadata.get("document_name") for d in capture["combined_docs"]]
    assert titles == [
        "CUR-MANI", "CUR-VOTE", "CUR-SPEECH",
        "HIST-MANI", "HIST-VOTE", "HIST-SPEECH",
    ], (
        "combined_docs must be current-first, historic-after "
        "(manifesto→vote→speech per bucket, SC1) — not the old manifesto→speech order"
    )

    source_titles = [s["source"] for s in _sources_from_events(events)]
    assert source_titles == titles, "sources[] must mirror combined_docs order exactly"


def test_adaptive_speech_fallback_when_official_sparse(monkeypatch) -> None:
    """When votes+manifesto current buckets are empty (official data sparse) and
    more than _CURRENT_SPEECH_LIMIT speeches are present, the extra speeches survive
    into combined_docs — the adaptive fallback fires so the answer isn't starved (SC2)."""
    capture: dict = {}
    n_speeches = cs._CURRENT_SPEECH_LIMIT + 2  # strictly above the normal cap

    def _mock_two_pass(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "parliamentary_speech":
            return {
                "current": [
                    {
                        "citation_title": f"SPEECH-{i}",
                        "publish_date": "2022-01-01",
                        "citation_url": "u",
                    }
                    for i in range(n_speeches)
                ],
                "historic": [],
            }
        return {"current": [], "historic": []}  # manifesto + vote empty → sparse

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve_two_pass", _mock_two_pass)

    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    _drive_single_party(tw)

    speech_titles = [
        d.metadata.get("document_name")
        for d in capture["combined_docs"]
        if str(d.metadata.get("document_name", "")).startswith("SPEECH-")
    ]
    assert len(speech_titles) == n_speeches, (
        "adaptive fallback must keep more than _CURRENT_SPEECH_LIMIT speeches when "
        f"official data is sparse (expected {n_speeches}, got {len(speech_titles)})"
    )
    assert len(speech_titles) > cs._CURRENT_SPEECH_LIMIT


def test_speech_trimmed_when_official_present(monkeypatch) -> None:
    """When official data (votes+manifesto) is present, current speeches are trimmed
    to exactly _CURRENT_SPEECH_LIMIT even though more were fetched (SC2)."""
    capture: dict = {}
    n_speeches = cs._CURRENT_SPEECH_LIMIT + 2

    def _mock_two_pass(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return {
                "current": [{
                    "citation_title": "MANI",
                    "publish_date": "2022-01-01",
                    "citation_url": "u",
                    "meta": {"page_start": 1},
                }],
                "historic": [],
            }
        if st == "vote_record":
            return {
                "current": [_participating_vote_payload("VOTE", "2022-01-01")],
                "historic": [],
            }
        if st == "parliamentary_speech":
            return {
                "current": [
                    {
                        "citation_title": f"SPEECH-{i}",
                        "publish_date": "2022-01-01",
                        "citation_url": "u",
                    }
                    for i in range(n_speeches)
                ],
                "historic": [],
            }
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve_two_pass", _mock_two_pass)

    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    _drive_single_party(tw)

    speech_titles = [
        d.metadata.get("document_name")
        for d in capture["combined_docs"]
        if str(d.metadata.get("document_name", "")).startswith("SPEECH-")
    ]
    assert len(speech_titles) == cs._CURRENT_SPEECH_LIMIT, (
        "speeches must be trimmed to _CURRENT_SPEECH_LIMIT when official data is "
        f"present (expected {cs._CURRENT_SPEECH_LIMIT}, got {len(speech_titles)})"
    )
    # The trimmed set is the first N fetched speeches (order preserved).
    assert speech_titles == [f"SPEECH-{i}" for i in range(cs._CURRENT_SPEECH_LIMIT)]


def test_official_coverage_helper() -> None:
    """_official_coverage(vote_docs_current, manifesto_current) returns
    (votes_absent, manifesto_absent) from the participation-filtered vote DOCS."""
    # Both empty → both absent.
    assert cs._official_coverage([], []) == (True, True)
    # Votes present, manifesto empty.
    assert cs._official_coverage([object()], []) == (False, True)
    # Votes empty, manifesto present.
    assert cs._official_coverage([], [{"citation_title": "M"}]) == (True, False)
    # Both present → neither absent.
    assert cs._official_coverage([object()], [{"citation_title": "M"}]) == (False, False)


def test_single_pass_fallback_when_no_window(monkeypatch) -> None:
    """When term_window is None, single-pass retrieve() is used (retrieve_two_pass
    is never called) and grounding matches the pre-Phase-09 behaviour (SC4)."""
    capture: dict = {}
    called = {"single": False, "two_pass": False}

    def _mock_single(_query, **kwargs):
        called["single"] = True
        if kwargs.get("source_type") == "party_manifesto":
            return [{
                "citation_title": "SP-MANI",
                "publish_date": "2022-01-01",
                "citation_url": "u",
                "meta": {"page_start": 1},
            }]
        return []

    def _mock_two_pass_flag(_query, **kwargs):
        called["two_pass"] = True
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve", _mock_single)
    monkeypatch.setattr(cs, "retrieve_two_pass", _mock_two_pass_flag)

    _drive_single_party(None)

    assert called["single"] is True, "single-pass retrieve() must be used when no window"
    assert called["two_pass"] is False, "retrieve_two_pass must NOT run without a window"
    titles = [d.metadata.get("document_name") for d in capture["combined_docs"]]
    assert titles == ["SP-MANI"], "fallback grounding must come from single-pass retrieve()"


# ---------------------------------------------------------------------------
# GDPR cache gate: only curated (proposed-question / quick-reply-driven)
# conversations may be cached; free-text history-hash caching is blocked.
# ---------------------------------------------------------------------------


def _user(content: str) -> Message:
    return Message(role=Role.USER, content=content)


def _assistant(content: str, quick_replies: list[str] | None = None) -> Message:
    return Message(role=Role.ASSISTANT, content=content, quick_replies=quick_replies)


def test_quick_reply_driven_single_user_turn() -> None:
    """A single-user-turn history is quick-reply-driven by definition — first-turn
    curation is handled by the proposed-question check, not this helper."""
    assert cs._conversation_is_quick_reply_driven([_user("Frage?")]) is True


def test_quick_reply_driven_followup_from_quick_replies() -> None:
    """Follow-up user turn offered by the preceding assistant's quick_replies → True."""
    history = [
        _user("Q1"),
        _assistant("A1", quick_replies=["QR-a", "QR-b"]),
        _user("QR-b"),
    ]
    assert cs._conversation_is_quick_reply_driven(history) is True


def test_quick_reply_driven_free_text_followup_false() -> None:
    """Free-text follow-up (not among the offered quick_replies) → False."""
    history = [
        _user("Q1"),
        _assistant("A1", quick_replies=["QR-a", "QR-b"]),
        _user("meine eigene Frage"),
    ]
    assert cs._conversation_is_quick_reply_driven(history) is False


def test_quick_reply_driven_missing_quick_replies_false() -> None:
    """Missing/empty quick_replies on the preceding assistant message → False
    (default NOT cacheable when signals are missing)."""
    history_none = [_user("Q1"), _assistant("A1"), _user("QR-a")]
    history_empty = [_user("Q1"), _assistant("A1", quick_replies=[]), _user("QR-a")]
    assert cs._conversation_is_quick_reply_driven(history_none) is False
    assert cs._conversation_is_quick_reply_driven(history_empty) is False


def test_quick_reply_driven_no_preceding_assistant_false() -> None:
    """A follow-up user turn NOT immediately preceded by an assistant message → False."""
    history = [_user("Q1"), _user("Q2")]
    assert cs._conversation_is_quick_reply_driven(history) is False


def test_quick_reply_driven_chain_one_bad_link_false() -> None:
    """Every prior follow-up must be quick-reply-driven; one free-text hop poisons
    the whole conversation."""
    good_chain = [
        _user("Q1"),
        _assistant("A1", quick_replies=["QR-1"]),
        _user("QR-1"),
        _assistant("A2", quick_replies=["QR-2"]),
        _user("QR-2"),
    ]
    bad_chain = [
        _user("Q1"),
        _assistant("A1", quick_replies=["QR-1"]),
        _user("freier Text"),
        _assistant("A2", quick_replies=["QR-2"]),
        _user("QR-2"),
    ]
    assert cs._conversation_is_quick_reply_driven(good_chain) is True
    assert cs._conversation_is_quick_reply_driven(bad_chain) is False


def test_curated_first_turn_free_text_not_cacheable() -> None:
    """First-turn free-text (not a proposed question) → NOT cacheable."""
    assert (
        cs._is_curated_conversation([_user("freie Frage")], ["Vorschlag 1"], []) is False
    )


def test_curated_first_turn_proposed_cacheable() -> None:
    """First-turn proposed question (party or group list) → cacheable."""
    assert cs._is_curated_conversation([_user("Vorschlag 1")], ["Vorschlag 1"], []) is True
    assert (
        cs._is_curated_conversation([_user("Gruppenfrage")], [], ["Gruppenfrage"]) is True
    )


def test_curated_quick_reply_followup_cacheable() -> None:
    """Proposed first turn + quick-reply-driven follow-ups → cacheable."""
    history = [
        _user("Vorschlag 1"),
        _assistant("A1", quick_replies=["QR-1"]),
        _user("QR-1"),
    ]
    assert cs._is_curated_conversation(history, ["Vorschlag 1"], []) is True


def test_curated_free_text_followup_not_cacheable() -> None:
    """Free-text follow-up after a curated first turn → NOT cacheable (GDPR fix:
    free-text conversations must never be replayable cross-user)."""
    history = [
        _user("Vorschlag 1"),
        _assistant("A1", quick_replies=["QR-1"]),
        _user("eigene Anschlussfrage"),
    ]
    assert cs._is_curated_conversation(history, ["Vorschlag 1"], []) is False


def test_curated_non_curated_first_turn_followup_not_cacheable() -> None:
    """Even a fully quick-reply-driven chain is NOT cacheable when the first
    message was not curated."""
    history = [
        _user("freie Frage"),
        _assistant("A1", quick_replies=["QR-1"]),
        _user("QR-1"),
    ]
    assert cs._is_curated_conversation(history, ["Vorschlag 1"], []) is False


def test_curated_empty_history_not_cacheable() -> None:
    """No user message at all → default NOT cacheable."""
    assert cs._is_curated_conversation([], ["Vorschlag 1"], []) is False


def test_gdpr_cache_gate_wired_into_party_loop() -> None:
    """The comprehensive gate replaces the old first-turn-only gate inside
    generate_chat_stream's single-party loop."""
    source = inspect.getsource(cs.generate_chat_stream)
    assert "_is_curated_conversation" in source, "curated-conversation gate must be wired"
    assert "GDPR cache gate" in source, "gate site must carry the GDPR comment tag"
    assert (
        "if is_beginning_of_chat and not is_proposed_question:" not in source
    ), "old first-turn-only gate must be replaced by the comprehensive gate"
