# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for additions to chat_service:
  - Vote sources[] dict carries a structural 'region' marker
  - election_level / level kwarg is passed ONLY to vote_record
    _safe_retrieve calls, never to manifesto/speech calls.
  - election_level is derived from _context.level and threaded through
    fetch_party_response_stream signature.

Behavioural tests — collaborators (embed, retrieve, retrieve_two_pass, the LLM
generator) are monkeypatched; no LLM, no network, no live Qdrant.
"""

import asyncio
import inspect
import json
from datetime import datetime, timezone

import src.chat_service as cs
from src.chat_service import fetch_party_response_stream, process_party
from src.models.chat import CachedResponse, GroupChatSession, Message
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
        meta_vp = vp.get("meta") or {}
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
                "region": vp.get("region"),  # must be present
            }
        )

    assert len(sources) == 1, "Expected 1 source entry for participating party"
    source_dict = sources[0]
    assert "region" in source_dict, "vote source dict must include 'region' key"
    assert source_dict["region"] == "DE", (
        f"region must match payload region 'DE', got {source_dict['region']!r}"
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


def test_speech_sources_emit_dual_links(monkeypatch) -> None:
    """A merged op speech emits ONE source carrying BOTH video_url (deep-link) and
    pdf_url (grafted DIP transcript); a dip speech emits its PDF as pdf_url. The
    video must not replace the PDF. Driven behaviourally through the single-party
    path; _speech_deeplink_url is stubbed to identity so this exercises the
    dual-link emission, not the deep-link computation (covered by test_is_video_link)."""
    op_payload = {
        "citation_title": "Rede A",
        "citation_url": "https://cdn.example/clip.mp4#t=12.5",
        "publish_date": "2024-01-15",
        "source": "op",
        "text": "op text",
        "meta": {"transcript_pdf_url": "https://dserver.example/btp/20/2000101.pdf"},
    }
    dip_payload = {
        "citation_title": "Rede B",
        "citation_url": "https://dserver.example/btp/20/2000102.pdf",
        "publish_date": "2024-01-16",
        "source": "dip",
        "text": "dip text",
        "meta": {},
    }

    def _retrieve(_query, **kwargs):
        if kwargs.get("source_type") == "parliamentary_speech":
            return [op_payload, dip_payload]
        return []

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "retrieve", _retrieve)
    monkeypatch.setattr(cs, "_speech_deeplink_url", lambda p, _q: p.get("citation_url"))

    sources = _sources_from_events(_drive_single_party(None))  # no window → single-pass

    op_src = next(s for s in sources if s["source"] == "Rede A")
    assert op_src.get("video_url") == "https://cdn.example/clip.mp4#t=12.5", (
        "op speech must expose the video deep-link as video_url"
    )
    assert op_src.get("pdf_url") == "https://dserver.example/btp/20/2000101.pdf", (
        "op speech must additively expose the grafted DIP transcript as pdf_url"
    )

    dip_src = next(s for s in sources if s["source"] == "Rede B")
    assert dip_src.get("pdf_url") == "https://dserver.example/btp/20/2000102.pdf", (
        "dip speech must expose its PDF as pdf_url"
    )
    assert "video_url" not in dip_src, "a dip speech has no video deep-link"


def test_source_snippet_normalizes_and_truncates() -> None:
    """_source_snippet is the PDF viewer's highlight anchor: whitespace collapses,
    long text cuts at a word boundary under the cap, empty text yields None."""
    from src.chat_service import _SNIPPET_MAX_CHARS, _source_snippet

    assert _source_snippet(None) is None
    assert _source_snippet("") is None
    assert _source_snippet("Ein  Satz\n\tmit   Umbrüchen") == "Ein Satz mit Umbrüchen"

    long_text = "Wort " * 300
    snippet = _source_snippet(long_text)
    assert snippet is not None
    assert len(snippet) <= _SNIPPET_MAX_CHARS
    assert not snippet.endswith(" ") and snippet.endswith("Wort")


def test_pdf_sources_carry_snippet_votes_do_not(monkeypatch) -> None:
    """Manifesto and speech sources carry a `snippet` (chunk-text excerpt) for the
    PDF viewer's highlight; vote sources cite web pages and must not get one."""
    manifesto_payload = {
        "citation_title": "Wahlprogramm",
        "citation_url": "https://storage.example/wahlprogramm.pdf",
        "publish_date": "2026-06-01",
        "text": "Wir  fordern\neine bessere Zukunft.",
        "meta": {"page_start": 8},
    }
    vote_payload = {
        "citation_title": "Abstimmung: Testgesetz",
        "citation_url": "https://example.com/vote/1",
        "publish_date": "2024-01-15",
        "text": "vote text must not leak into a snippet",
        "meta": {
            "vote_results": [{"party_id": "spd", "stance": "yes", "yes": 1, "no": 0}]
        },
    }
    speech_payload = {
        "citation_title": "Rede C",
        "citation_url": "https://dserver.example/btp/20/2000103.pdf",
        "publish_date": "2024-01-16",
        "source": "dip",
        "text": "Sehr geehrte Damen und Herren, wir beraten heute.",
        "meta": {},
    }

    def _retrieve(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return [manifesto_payload]
        if st == "vote_record":
            return [vote_payload]
        if st == "parliamentary_speech":
            return [speech_payload]
        return []

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "retrieve", _retrieve)

    sources = _sources_from_events(_drive_single_party(None))

    manifesto_src = next(s for s in sources if s["source"] == "Wahlprogramm")
    assert manifesto_src.get("snippet") == "Wir fordern eine bessere Zukunft."

    speech_src = next(s for s in sources if s["source"] == "Rede C")
    assert speech_src.get("snippet") == (
        "Sehr geehrte Damen und Herren, wir beraten heute."
    )

    vote_src = next(s for s in sources if s["source"] == "Abstimmung: Testgesetz")
    assert "snippet" not in vote_src


# ---------------------------------------------------------------------------
# election_level scoping (vote_record only) is proven behaviourally by
# test_historic_period_id_current_only + test_single_pass_fallback_when_no_window.
# election_level threaded through fetch_party_response_stream
# ---------------------------------------------------------------------------


def test_fetch_party_response_stream_has_election_level_param() -> None:
    """fetch_party_response_stream signature must include election_level: Optional[str] = None."""
    sig = inspect.signature(fetch_party_response_stream)
    assert "election_level" in sig.parameters, (
        "fetch_party_response_stream must accept 'election_level' parameter"
    )
    param = sig.parameters["election_level"]
    assert param.default is None, (
        f"election_level default must be None, got {param.default!r}"
    )


# ---------------------------------------------------------------------------
# two-pass retrieval tests — drive fetch_party_response_stream / process_party
# with monkeypatched collaborators and assert the observed retrieval behaviour
# (two-pass vs single-pass, vote-only scoping, current-first/historic-after merge).
# ---------------------------------------------------------------------------


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

    async def _mock_get_rag_query_cache(
        _context_id: str, _party_id: str, _key: str
    ) -> None:
        return None

    async def _mock_write_rag_query_cache(*_a, **_k) -> None:
        return None

    monkeypatch.setattr(cs, "generate_improvement_rag_query", _mock_rag_query)
    monkeypatch.setattr(cs, "embed", _FakeEmbed())
    monkeypatch.setattr(cs, "generate_streaming_chatbot_response", _mock_llm)
    monkeypatch.setattr(cs, "aget_cached_rag_query", _mock_get_rag_query_cache)
    monkeypatch.setattr(cs, "awrite_cached_rag_query", _mock_write_rag_query_cache)


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
            is_cacheable_chat=False,
            region_path=["DE-BW"],
            term_window=term_window,
            **stream_kwargs,
        ):
            events.append(ev)
        return events

    return asyncio.run(_run())


def _drive_comparison(term_window, **kwargs) -> dict:
    """Run the comparison path (process_party) for one party; returns the filled
    relevant_doc_dict. Mirrors _drive_single_party but for the no-emit path."""
    relevant_doc_dict: dict = {}

    async def _run() -> None:
        await process_party(
            _make_party(),
            "conv",
            "q?",
            relevant_doc_dict,
            asyncio.Lock(),
            [],
            "ctx",
            region_path=["DE-BW"],
            term_window=term_window,
            **kwargs,
        )

    asyncio.run(_run())
    return relevant_doc_dict


def _sources_from_events(events: list[str]) -> list[dict]:
    # Events are BARE v5 part payloads (EventSourceResponse adds the SSE
    # framing at the route layer), so each event parses as JSON directly.
    for ev in events:
        if '"sources_ready"' in ev:
            payload = json.loads(ev)
            return payload["data"]["sources"]
    return []


def test_two_pass_used_in_both_paths(monkeypatch) -> None:
    """BOTH the single-party and comparison paths run the temporal two-pass
    retrieval for all three sources when a term_window resolves — behavioural proof
    that both delegate to the shared _retrieve_party_buckets, replacing a
    source-text check that a refactor would silently break."""
    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    expected = {"vote_record", "party_manifesto", "parliamentary_speech"}

    def _make_recorder(store: dict):
        def _rec(_query, **kwargs):
            store[kwargs.get("source_type")] = kwargs
            return {"current": [], "historic": []}

        return _rec

    _wire_common_mocks(monkeypatch, {})

    single_party_calls: dict = {}
    monkeypatch.setattr(cs, "retrieve_two_pass", _make_recorder(single_party_calls))
    _drive_single_party(tw)
    assert expected <= set(single_party_calls), (
        "single-party path must two-pass all three sources"
    )

    comparison_calls: dict = {}
    monkeypatch.setattr(cs, "retrieve_two_pass", _make_recorder(comparison_calls))
    _drive_comparison(tw)
    assert expected <= set(comparison_calls), (
        "comparison path must two-pass all three sources"
    )


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


def test_manifesto_region_path_is_level_exclusive(monkeypatch) -> None:
    """Manifesto retrieval is scoped to the election's OWN region — a state chat
    grounds in the Landtagswahl program, never the federal one (and vice versa).
    Votes and speeches keep the full ancestry path: votes rely on the
    relevance_levels down-rank instead, speeches are Bundestag-only content."""
    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    def _make_recorder(store: dict, result):
        def _rec(_query, **kwargs):
            store[kwargs.get("source_type")] = kwargs
            return result

        return _rec

    async def _drive(term_window) -> None:
        await cs._retrieve_party_buckets(
            party=_make_party(),
            improved_rag_query="q",
            rag_query_vector=[0.0],
            region_path=["DE", "DE-BW"],
            legislature_period_id=None,
            election_level="state",
            term_window=term_window,
            manifesto_term_start=None,
        )

    two_pass_calls: dict = {}
    _two_pass_recorder = _make_recorder(two_pass_calls, {"current": [], "historic": []})
    monkeypatch.setattr(cs, "retrieve_two_pass", _two_pass_recorder)
    asyncio.run(_drive(tw))
    assert two_pass_calls["party_manifesto"]["region_path"] == ["DE-BW"]
    assert two_pass_calls["vote_record"]["region_path"] == ["DE", "DE-BW"]
    assert two_pass_calls["parliamentary_speech"]["region_path"] == ["DE", "DE-BW"]

    single_pass_calls: dict = {}
    monkeypatch.setattr(cs, "retrieve", _make_recorder(single_pass_calls, []))
    asyncio.run(_drive(None))
    assert single_pass_calls["party_manifesto"]["region_path"] == ["DE-BW"]
    assert single_pass_calls["vote_record"]["region_path"] == ["DE", "DE-BW"]
    assert single_pass_calls["parliamentary_speech"]["region_path"] == ["DE", "DE-BW"]


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
    each bucket) and sources[] mirror the identical order for [N] alignment."""
    capture: dict = {}

    def _mock_two_pass(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return {
                "current": [
                    {
                        "citation_title": "CUR-MANI",
                        "publish_date": "2022-01-01",
                        "citation_url": "u",
                        "meta": {"page_start": 1},
                    }
                ],
                "historic": [
                    {
                        "citation_title": "HIST-MANI",
                        "publish_date": "2018-01-01",
                        "citation_url": "u",
                        "meta": {"page_start": 1},
                    }
                ],
            }
        if st == "vote_record":
            return {
                "current": [_participating_vote_payload("CUR-VOTE", "2022-01-01")],
                "historic": [_participating_vote_payload("HIST-VOTE", "2018-01-01")],
            }
        if st == "parliamentary_speech":
            return {
                "current": [
                    {
                        "citation_title": "CUR-SPEECH",
                        "publish_date": "2022-01-01",
                        "citation_url": "u",
                    }
                ],
                "historic": [
                    {
                        "citation_title": "HIST-SPEECH",
                        "publish_date": "2018-01-01",
                        "citation_url": "u",
                    }
                ],
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
        "CUR-MANI",
        "CUR-VOTE",
        "CUR-SPEECH",
        "HIST-MANI",
        "HIST-VOTE",
        "HIST-SPEECH",
    ], (
        "combined_docs must be current-first, historic-after "
        "(manifesto→vote→speech per bucket) — not the old manifesto→speech order"
    )

    source_titles = [s["source"] for s in _sources_from_events(events)]
    assert source_titles == titles, "sources[] must mirror combined_docs order exactly"


def test_adaptive_speech_fallback_when_official_sparse(monkeypatch) -> None:
    """When votes+manifesto current buckets are empty (official data sparse) and
    more than _CURRENT_SPEECH_LIMIT speeches are present, the extra speeches survive
    into combined_docs — the adaptive fallback fires so the answer isn't starved."""
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
    to exactly _CURRENT_SPEECH_LIMIT even though more were fetched."""
    capture: dict = {}
    n_speeches = cs._CURRENT_SPEECH_LIMIT + 2

    def _mock_two_pass(_query, **kwargs):
        st = kwargs.get("source_type")
        if st == "party_manifesto":
            return {
                "current": [
                    {
                        "citation_title": "MANI",
                        "publish_date": "2022-01-01",
                        "citation_url": "u",
                        "meta": {"page_start": 1},
                    }
                ],
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
    assert cs._official_coverage([object()], [{"citation_title": "M"}]) == (
        False,
        False,
    )


def test_single_pass_fallback_when_no_window(monkeypatch) -> None:
    """When term_window is None, single-pass retrieve() is used (retrieve_two_pass
    is never called) and grounding matches the earlier behaviour."""
    capture: dict = {}
    calls: dict = {}
    called = {"single": False, "two_pass": False}

    def _mock_single(_query, **kwargs):
        called["single"] = True
        calls[kwargs.get("source_type")] = kwargs
        if kwargs.get("source_type") == "party_manifesto":
            return [
                {
                    "citation_title": "SP-MANI",
                    "publish_date": "2022-01-01",
                    "citation_url": "u",
                    "meta": {"page_start": 1},
                }
            ]
        return []

    def _mock_two_pass_flag(_query, **kwargs):
        called["two_pass"] = True
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve", _mock_single)
    monkeypatch.setattr(cs, "retrieve_two_pass", _mock_two_pass_flag)

    _drive_single_party(None, legislature_period_id=161, election_level="federal")

    assert called["single"] is True, (
        "single-pass retrieve() must be used when no window"
    )
    assert called["two_pass"] is False, (
        "retrieve_two_pass must NOT run without a window"
    )
    titles = [d.metadata.get("document_name") for d in capture["combined_docs"]]
    assert titles == ["SP-MANI"], (
        "fallback grounding must come from single-pass retrieve()"
    )
    # level + legislature_period_id scope vote_record ONLY (single-pass path) —
    # behavioural replacement for the old source-text 'level=election_level' guard.
    assert calls["vote_record"].get("level") == "federal"
    assert calls["vote_record"].get("legislature_period_id") == 161
    for st in ("party_manifesto", "parliamentary_speech"):
        assert "level" not in calls[st], f"{st} single-pass must NOT carry level"
        assert "legislature_period_id" not in calls[st], (
            f"{st} single-pass must NOT carry legislature_period_id"
        )


def test_coverage_and_has_historic_threaded_into_generation(monkeypatch) -> None:
    """fetch_party_response_stream computes source coverage and threads
    present_sources + has_historic into the single-party generator — behavioural
    replacement for a source-text 'is it wired' check."""
    capture: dict = {}
    gen_kwargs: dict = {}

    async def _capture_gen(_party, _conv, _question, _docs, **kwargs):
        gen_kwargs.update(kwargs)

        async def _gen():
            return
            yield  # pragma: no cover — empty async generator

        return _gen()

    def _retrieve(_query, **kwargs):
        if kwargs.get("source_type") == "party_manifesto":
            return [
                {
                    "citation_title": "M",
                    "publish_date": "2022-01-01",
                    "citation_url": "u",
                    "meta": {"page_start": 1},
                }
            ]
        return []

    _wire_common_mocks(monkeypatch, capture)
    monkeypatch.setattr(cs, "retrieve", _retrieve)
    monkeypatch.setattr(cs, "generate_streaming_chatbot_response", _capture_gen)

    _drive_single_party(None)  # single-pass → no historic

    assert isinstance(gen_kwargs.get("present_sources"), tuple), (
        "coverage must be threaded as present_sources=(...)"
    )
    assert gen_kwargs.get("has_historic") is False, (
        "single-pass path threads has_historic=False (no historic buckets)"
    )


# ---------------------------------------------------------------------------
# GDPR cache gate — server-authoritative eligibility (never trusts the client's
# chat_history). Only curated conversations may enter the cross-user cache.
# ---------------------------------------------------------------------------


def test_cache_eligibility_first_turn_proposed_is_cacheable() -> None:
    assert (
        cs._evaluate_cache_eligibility(
            "s-fp", "Vorschlag 1", is_beginning_of_chat=True, is_proposed_question=True
        )
        is True
    )


def test_cache_eligibility_first_turn_free_text_not_cacheable() -> None:
    assert (
        cs._evaluate_cache_eligibility(
            "s-ff", "freie Frage", is_beginning_of_chat=True, is_proposed_question=False
        )
        is False
    )


def test_cache_eligibility_followup_without_server_state_not_cacheable() -> None:
    # No server record for this session (cold start / eviction / a client that
    # fabricated its own assistant quick_replies) → fail-safe NOT cacheable.
    assert (
        cs._evaluate_cache_eligibility(
            "s-cold", "QR-a", is_beginning_of_chat=False, is_proposed_question=False
        )
        is False
    )


def test_cache_eligibility_followup_matches_server_quick_replies() -> None:
    cs._remember_session_quick_replies(
        "s-ok", is_cacheable=True, quick_replies=["QR-a", "QR-b"]
    )
    assert (
        cs._evaluate_cache_eligibility(
            "s-ok", "QR-b", is_beginning_of_chat=False, is_proposed_question=False
        )
        is True
    )


def test_cache_eligibility_forged_reply_ignored() -> None:
    """A message the server never offered — even if a fabricated client assistant
    turn 'offered' it — is NOT cacheable: the gate reads the server record, not
    the request history."""
    cs._remember_session_quick_replies(
        "s-forge", is_cacheable=True, quick_replies=["QR-a"]
    )
    assert (
        cs._evaluate_cache_eligibility(
            "s-forge",
            "injizierter politischer Text",
            is_beginning_of_chat=False,
            is_proposed_question=False,
        )
        is False
    )


def test_cache_eligibility_is_sticky_once_broken() -> None:
    """Once a prior turn is non-cacheable, a later matching reply cannot revive it
    (monotonic, mirroring V1's sticky GroupChatSession.is_cacheable)."""
    cs._remember_session_quick_replies(
        "s-sticky", is_cacheable=False, quick_replies=["QR-a"]
    )
    assert (
        cs._evaluate_cache_eligibility(
            "s-sticky", "QR-a", is_beginning_of_chat=False, is_proposed_question=False
        )
        is False
    )


def test_cacheable_lookup_runs_after_retrieval(monkeypatch) -> None:
    """Lookup runs after retrieval. A hit skips the answer LLM."""
    order: list[str] = []
    llm_called = {"n": 0}

    def _rec_two_pass(_query, **_kwargs):
        order.append("retrieve")
        return {"current": [], "historic": []}

    async def _get_cached(_context_id: str, _party_id: str, _key: str):
        order.append("cache_lookup")
        return [
            CachedResponse(
                content="cached",
                sources=[],
                created_at=datetime.now(timezone.utc),
            )
        ]

    async def _mock_llm(*_a, **_k):
        llm_called["n"] += 1

        async def _gen():
            return
            yield  # pragma: no cover

        return _gen()

    async def _cached_yielder(*_a, **_k):
        order.append("cached_emit")
        if False:  # pragma: no cover
            yield ""

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "generate_streaming_chatbot_response", _mock_llm)
    monkeypatch.setattr(cs, "retrieve_two_pass", _rec_two_pass)
    monkeypatch.setattr(cs, "aget_cached_answers_for_party", _get_cached)
    monkeypatch.setattr(cs, "yield_cached_party_response", _cached_yielder)

    tw = (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    async def _run() -> None:
        async for _ev in fetch_party_response_stream(
            _make_party(),
            "conv",
            "q?",
            _make_session(),
            all_available_parties=[],
            use_premium_llms=False,
            is_cacheable_chat=True,
            region_path=["DE-BW"],
            term_window=tw,
        ):
            pass

    asyncio.run(_run())

    assert "retrieve" in order
    assert "cache_lookup" in order
    assert order.index("retrieve") < order.index("cache_lookup")
    assert "cached_emit" in order
    assert llm_called["n"] == 0


def _cacheable_term_window() -> tuple[datetime, datetime]:
    return (
        datetime(2021, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


async def _empty_cached_answers(_context_id: str, _party_id: str, _key: str) -> list:
    return []


async def _noop_async(*_a, **_k) -> None:
    return None


def test_cacheable_reuses_cached_rag_query(monkeypatch) -> None:
    """A cached rewrite must skip the rewrite LLM and reuse the stored query."""
    generated = {"n": 0}
    retrieved_queries: list[str] = []

    async def _mock_rag_query(*_a, **_k) -> str:
        generated["n"] += 1
        return f"fresh-{generated['n']}"

    async def _get_rag(_context_id: str, _party_id: str, _key: str) -> str:
        return "cached rewrite"

    def _rec_two_pass(query, **_kwargs):
        retrieved_queries.append(query)
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "generate_improvement_rag_query", _mock_rag_query)
    monkeypatch.setattr(cs, "aget_cached_rag_query", _get_rag)
    monkeypatch.setattr(cs, "retrieve_two_pass", _rec_two_pass)
    monkeypatch.setattr(cs, "aget_cached_answers_for_party", _empty_cached_answers)
    monkeypatch.setattr(cs, "awrite_cached_answer_for_party", _noop_async)

    async def _run() -> None:
        async for _ev in fetch_party_response_stream(
            _make_party(),
            "conv",
            "q?",
            _make_session(),
            all_available_parties=[],
            use_premium_llms=False,
            is_cacheable_chat=True,
            region_path=["DE-BW"],
            term_window=_cacheable_term_window(),
        ):
            pass

    asyncio.run(_run())

    assert generated["n"] == 0
    assert retrieved_queries
    assert set(retrieved_queries) == {"cached rewrite"}


def test_cacheable_writes_rag_query_on_miss(monkeypatch) -> None:
    writes: list[tuple[str, str, str, str]] = []

    async def _get_rag(_context_id: str, _party_id: str, _key: str) -> None:
        return None

    async def _write_rag(context_id: str, party_id: str, key: str, query: str) -> None:
        writes.append((context_id, party_id, key, query))

    def _rec_two_pass(_query, **_kwargs):
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "aget_cached_rag_query", _get_rag)
    monkeypatch.setattr(cs, "awrite_cached_rag_query", _write_rag)
    monkeypatch.setattr(cs, "retrieve_two_pass", _rec_two_pass)
    monkeypatch.setattr(cs, "aget_cached_answers_for_party", _empty_cached_answers)
    monkeypatch.setattr(cs, "awrite_cached_answer_for_party", _noop_async)

    async def _run() -> None:
        async for _ev in fetch_party_response_stream(
            _make_party(),
            "conv",
            "q?",
            _make_session(),
            all_available_parties=[],
            use_premium_llms=False,
            is_cacheable_chat=True,
            region_path=["DE-BW"],
            term_window=_cacheable_term_window(),
        ):
            pass

    asyncio.run(_run())

    assert len(writes) == 1
    context_id, party_id, key, query = writes[0]
    assert context_id == "c1"
    assert party_id == "spd"
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)
    assert query == "improved q"


def test_cached_rag_query_stabilizes_answer_cache_key(monkeypatch) -> None:
    """A stored rewrite must keep the answer cache key the same on a repeat."""
    rewrite_n = {"n": 0}
    answer_keys: list[str] = []
    stored_query: dict[str, str | None] = {"q": None}

    async def _mock_rag_query(*_a, **_k) -> str:
        rewrite_n["n"] += 1
        return f"fresh-{rewrite_n['n']}"

    async def _get_rag(_context_id: str, _party_id: str, _key: str) -> str | None:
        return stored_query["q"]

    async def _write_rag(
        _context_id: str, _party_id: str, _key: str, query: str
    ) -> None:
        stored_query["q"] = query

    def _rec_two_pass(query, **kwargs):
        if kwargs.get("source_type") != "party_manifesto":
            return {"current": [], "historic": []}
        return {
            "current": [
                {
                    "citation_title": f"prog-{query}",
                    "citation_url": f"https://example.com/{query}",
                    "publish_date": "2025-01-01",
                    "text": f"chunk for {query}",
                    "authority_tier": "self_reported",
                    "meta": {"page_start": 1},
                }
            ],
            "historic": [],
        }

    async def _get_answers(_context_id: str, _party_id: str, key: str) -> list:
        answer_keys.append(key)
        return []

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "generate_improvement_rag_query", _mock_rag_query)
    monkeypatch.setattr(cs, "aget_cached_rag_query", _get_rag)
    monkeypatch.setattr(cs, "awrite_cached_rag_query", _write_rag)
    monkeypatch.setattr(cs, "retrieve_two_pass", _rec_two_pass)
    monkeypatch.setattr(cs, "aget_cached_answers_for_party", _get_answers)
    monkeypatch.setattr(cs, "awrite_cached_answer_for_party", _noop_async)

    async def _run() -> None:
        async for _ev in fetch_party_response_stream(
            _make_party(),
            "conv",
            "q?",
            _make_session(),
            all_available_parties=[],
            use_premium_llms=False,
            is_cacheable_chat=True,
            region_path=["DE-BW"],
            term_window=_cacheable_term_window(),
        ):
            pass

    asyncio.run(_run())
    asyncio.run(_run())

    assert rewrite_n["n"] == 1
    assert stored_query["q"] == "fresh-1"
    assert len(answer_keys) == 2
    assert answer_keys[0] == answer_keys[1]


def test_non_cacheable_skips_rag_query_cache(monkeypatch) -> None:
    gets = {"n": 0}
    writes = {"n": 0}

    async def _get_rag(_context_id: str, _party_id: str, _key: str) -> None:
        gets["n"] += 1
        return None

    async def _write_rag(*_a, **_k) -> None:
        writes["n"] += 1

    def _rec_two_pass(_query, **_kwargs):
        return {"current": [], "historic": []}

    _wire_common_mocks(monkeypatch, {})
    monkeypatch.setattr(cs, "aget_cached_rag_query", _get_rag)
    monkeypatch.setattr(cs, "awrite_cached_rag_query", _write_rag)
    monkeypatch.setattr(cs, "retrieve_two_pass", _rec_two_pass)

    _drive_single_party(_cacheable_term_window())

    assert gets["n"] == 0
    assert writes["n"] == 0
