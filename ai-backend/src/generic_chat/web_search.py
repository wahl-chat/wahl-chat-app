# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Web search over the Perplexity Search API (POST /search).

Perplexity only has an allowlist (``search_domain_filter``), so "prefer our
outlets" is built here: one call restricted to the preferred outlets and one
open call, merged with the preferred results first.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic_ai.framing import neutralize_tags, register_tag

from src.generic_chat.schemas import WebResult
from wahlchat_common.answer_rules import CIVIC_DOMAINS, PREFERRED_OUTLETS

logger = logging.getLogger(__name__)

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
_TIMEOUT_S = 8.0
_MAX_RESULTS_PER_CALL = 10
MAX_PREFERRED = 5
MAX_OTHERS = 3
_SNIPPET_MAX_CHARS = 500

WEB_SNIPPET_TAG = register_tag("web_snippet")

_TITLE_CHARS = 200

Scope = Literal["news", "civic"]


def safe_title(title: str) -> str:
    """A page title is the site's text too: no framing tags, bounded."""
    return neutralize_tags(" ".join(title.split()))[:_TITLE_CHARS]
Recency = Literal["day", "week", "month", "year"]


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _in_domains(url: str, domains: tuple[str, ...]) -> bool:
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in domains)


# Perplexity takes at most this many entries in search_domain_filter.
MAX_FILTER_DOMAINS = 20


def domain_groups(domains: tuple[str, ...]) -> list[tuple[str, ...]]:
    """``domains`` in filter-sized groups, searched side by side."""
    return [
        domains[start : start + MAX_FILTER_DOMAINS]
        for start in range(0, len(domains), MAX_FILTER_DOMAINS)
    ]


def _dedup_key(url: str) -> str:
    parts = urlsplit(url)
    host = domain_of(url)
    return urlunsplit(("", host, parts.path.rstrip("/"), parts.query, ""))


def _payload(
    query: str, domains: Optional[tuple[str, ...]], recency: Optional[Recency]
) -> dict:
    # The model's query (written from the user's question) and fixed filters.
    payload: dict = {
        "query": query,
        "max_results": _MAX_RESULTS_PER_CALL,
        "country": "DE",
        "search_language_filter": ["de"],
    }
    if domains:
        if len(domains) > MAX_FILTER_DOMAINS:
            raise ValueError(f"{len(domains)} domains; split with domain_groups")
        payload["search_domain_filter"] = list(domains)
    if recency:
        payload["search_recency_filter"] = recency
    return payload


async def _call(client: httpx.AsyncClient, api_key: str, payload: dict) -> list[dict]:
    response = await client.post(
        PERPLEXITY_SEARCH_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=_TIMEOUT_S,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    return [r for r in results if isinstance(r, dict) and r.get("url")]


def _to_result(raw: dict, preferred: bool) -> WebResult:
    snippet = " ".join(str(raw.get("snippet") or "").split())[:_SNIPPET_MAX_CHARS]
    return WebResult(
        title=str(raw.get("title") or domain_of(raw["url"])),
        url=raw["url"],
        snippet=snippet,
        date=raw.get("date") or raw.get("last_updated"),
        domain=domain_of(raw["url"]),
        preferred=preferred,
    )


def merge_news(preferred_raw: list[dict], open_raw: list[dict]) -> list[WebResult]:
    """≤5 preferred-outlet results first, then ≤3 others, de-duplicated by URL.

    An open-web hit on a preferred outlet counts as preferred.
    """
    seen: set[str] = set()
    preferred: list[WebResult] = []
    others: list[WebResult] = []
    for raw in [*preferred_raw, *open_raw]:
        key = _dedup_key(raw["url"])
        if key in seen:
            continue
        seen.add(key)
        if _in_domains(raw["url"], PREFERRED_OUTLETS):
            if len(preferred) < MAX_PREFERRED:
                preferred.append(_to_result(raw, preferred=True))
        elif len(others) < MAX_OTHERS:
            others.append(_to_result(raw, preferred=False))
    return preferred + others


async def search_web(
    query: str,
    scope: Scope,
    recency: Optional[Recency] = None,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> tuple[list[WebResult], Optional[str]]:
    """Results plus a note for the model when the search was degraded.

    Never raises: a failed search must not end the turn.
    """
    api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        logger.warning("web_search: PERPLEXITY_API_KEY is not set")
        return [], "Web search is unavailable right now."

    owns_client = client is None
    http = client or httpx.AsyncClient()
    try:
        if scope == "civic":
            raw = await _call(http, api_key, _payload(query, CIVIC_DOMAINS, recency))
            # Civic sites are official sources, not news outlets: never flagged.
            results = [
                _to_result(r, preferred=True)
                for r in raw
                if _in_domains(r["url"], CIVIC_DOMAINS)
            ][: MAX_PREFERRED + MAX_OTHERS]
            return results, None

        groups = domain_groups(PREFERRED_OUTLETS)
        outcomes = await asyncio.gather(
            *(_call(http, api_key, _payload(query, group, recency)) for group in groups),
            _call(http, api_key, _payload(query, None, recency)),
            return_exceptions=True,
        )
        calls: list[list[dict]] = []
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                logger.warning("web_search: Perplexity call failed: %s", outcome)
                calls.append([])
            else:
                calls.append(outcome)
        if all(isinstance(o, BaseException) for o in outcomes):
            return [], "Web search failed; answer without web sources."
        preferred = [raw for found in calls[:-1] for raw in found]
        return merge_news(preferred, calls[-1]), None
    except Exception as exc:  # noqa: BLE001 (degrade, never end the turn)
        logger.warning("web_search: Perplexity search failed: %s", exc)
        return [], "Web search failed; answer without web sources."
    finally:
        if owns_client:
            await http.aclose()


async def search_sites(
    query: str, domains: tuple[str, ...], recency: Optional[Recency] = None
) -> tuple[list[WebResult], Optional[str]]:
    """One call restricted to ``domains``; results outside them are dropped.
    Never raises."""
    api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        return [], "Web search is unavailable right now."
    try:
        async with httpx.AsyncClient() as http:
            outcomes = await asyncio.gather(
                *(
                    _call(http, api_key, _payload(query, group, recency))
                    for group in domain_groups(domains)
                ),
                return_exceptions=True,
            )
    except Exception as exc:  # noqa: BLE001 (degrade, never end the turn)
        logger.warning("web_search: site search failed: %s", exc)
        return [], "Web search failed; answer without web sources."
    found = [o for o in outcomes if not isinstance(o, BaseException)]
    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            logger.warning("web_search: site search failed: %s", outcome)
    if not found:
        return [], "Web search failed; answer without web sources."
    seen: set[str] = set()
    results: list[WebResult] = []
    for raw in (r for group in found for r in group):
        key = _dedup_key(raw["url"])
        if key in seen or not _in_domains(raw["url"], domains):
            continue
        seen.add(key)
        results.append(_to_result(raw, preferred=True))
    return results, None
