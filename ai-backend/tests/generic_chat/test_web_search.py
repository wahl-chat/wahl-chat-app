# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Perplexity Search API client over a mocked transport (AC-11)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from src.generic_chat import web_search as web
from wahlchat_common.answer_rules import CIVIC_DOMAINS, PREFERRED_OUTLETS

_ALLOWED_KEYS = {
    "query",
    "max_results",
    "country",
    "search_language_filter",
    "search_domain_filter",
    "search_recency_filter",
}


def _result(url: str, title: str = "t") -> dict:
    return {"title": title, "url": url, "snippet": "s", "date": "2026-11-13"}


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")


class _Recorder:
    def __init__(self, preferred: list[dict], open_web: list[dict]) -> None:
        self.payloads: list[dict] = []
        self.headers: list[httpx.Headers] = []
        self._preferred = preferred
        self._open = open_web
        self._both_arrived = asyncio.Event()

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        self.payloads.append(payload)
        self.headers.append(request.headers)
        if len(self.payloads) == 2:
            self._both_arrived.set()
        # Each call waits for the other: passes only if both are in flight at once.
        await asyncio.wait_for(self._both_arrived.wait(), timeout=2)
        results = self._preferred if "search_domain_filter" in payload else self._open
        return httpx.Response(200, json={"id": "x", "results": results})


async def test_news_runs_two_parallel_calls_and_merges() -> None:
    preferred = [_result(f"https://www.tagesschau.de/a{i}") for i in range(7)]
    open_web = [
        _result("https://tagesschau.de/a0/"),  # duplicate of a preferred hit
        _result("https://www.zeit.de/x"),  # preferred outlet found by the open call
        *[_result(f"https://blog{i}.example/p") for i in range(5)],
    ]
    recorder = _Recorder(preferred, open_web)
    async with httpx.AsyncClient(transport=httpx.MockTransport(recorder)) as client:
        results, note = await web.search_web(
            "Mietpreisbremse Bundestag", "news", "week", client=client
        )

    assert note is None
    filtered = [p for p in recorder.payloads if "search_domain_filter" in p]
    assert len(recorder.payloads) == len(filtered) + 1
    # Every preferred outlet is searched, in filters Perplexity accepts.
    searched = [d for p in filtered for d in p["search_domain_filter"]]
    assert searched == list(PREFERRED_OUTLETS)
    assert all(len(p["search_domain_filter"]) <= web.MAX_FILTER_DOMAINS for p in filtered)
    for payload in recorder.payloads:
        assert payload["query"] == "Mietpreisbremse Bundestag"
        assert set(payload) <= _ALLOWED_KEYS
        assert payload["search_recency_filter"] == "week"
    assert all(h["authorization"] == "Bearer test-key" for h in recorder.headers)

    preferred_hits = [r for r in results if r.preferred]
    others = [r for r in results if not r.preferred]
    assert len(preferred_hits) == web.MAX_PREFERRED
    assert len(others) == web.MAX_OTHERS
    assert results[: web.MAX_PREFERRED] == preferred_hits  # preferred first
    assert len({r.url.rstrip("/").replace("www.", "") for r in results}) == len(results)


def test_merge_counts_open_hits_on_preferred_outlets_as_preferred() -> None:
    merged = web.merge_news([], [_result("https://www.zeit.de/x"), _result("https://b.example/y")])
    assert [(r.domain, r.preferred) for r in merged] == [("zeit.de", True), ("b.example", False)]


async def test_civic_searches_only_the_official_domains() -> None:
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"results": [_result("https://www.bpb.de/x"), _result("https://evil.example/y")]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results, _ = await web.search_web("Wie funktioniert der Bundesrat", "civic", client=client)

    assert len(payloads) == 1
    assert payloads[0]["search_domain_filter"] == list(CIVIC_DOMAINS)
    assert payloads[0]["query"] == "Wie funktioniert der Bundesrat"
    assert [r.domain for r in results] == ["bpb.de"]


async def test_failure_returns_empty_with_a_note() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results, note = await web.search_web("x y", "news", client=client)
    assert results == [] and note


async def test_one_failed_call_keeps_the_other() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "search_domain_filter" in json.loads(request.content):
            return httpx.Response(503)
        return httpx.Response(200, json={"results": [_result("https://a.example/1")]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results, note = await web.search_web("x y", "news", client=client)
    assert [r.domain for r in results] == ["a.example"] and note is None


async def test_missing_key_makes_no_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PERPLEXITY_API_KEY")

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request without a key")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results, note = await web.search_web("x y", "news", client=client)
    assert results == [] and note


def test_long_domain_lists_split_without_losing_one() -> None:
    domains = tuple(f"site{i}.de" for i in range(45))
    groups = web.domain_groups(domains)
    assert [len(g) for g in groups] == [20, 20, 5]
    assert [d for g in groups for d in g] == list(domains)
    with pytest.raises(ValueError):
        web._payload("x", domains, None)


async def test_a_site_search_covers_every_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.generic_chat import web_context

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        group = json.loads(request.content)["search_domain_filter"]
        seen.extend(group)
        return httpx.Response(200, json={"results": [_result(f"https://www.{group[-1]}/a")]})

    class Client(httpx.AsyncClient):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(web.httpx, "AsyncClient", Client)
    results, note = await web.search_sites("x y", web_context.PRESS_SITES)
    assert note is None and seen == list(web_context.PRESS_SITES)
    assert len(results) == len(web.domain_groups(web_context.PRESS_SITES))

