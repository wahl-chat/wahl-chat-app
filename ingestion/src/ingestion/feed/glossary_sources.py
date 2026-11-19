# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The official pages a glossary explanation rests on.

An explanation is written from these pages and checked against them, never
from the model's own knowledge alone, and the web links the first of them.
Only the Bundestag, the federal government and the Bundeszentrale für
politische Bildung count: they explain parliamentary terms neutrally and
keep their pages up.

The pages are found by a model searching the web (Google Search grounding),
then read here: the search's own summary is a pointer, not evidence.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

import requests
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict

from ingestion.feed.calendar import fetch_page
from ingestion.feed.prompts import format_research_prompt

logger = logging.getLogger(__name__)

ALLOWED_SOURCE_DOMAINS = ("bundestag.de", "bundesregierung.de", "bpb.de")
# Speeches and press releases on those sites are a government's or a party's
# voice, not an explanation, even when the search ranks them; archived pages
# may state rules since changed.
_EXCLUDED_PATH_PARTS = (
    "/bulletin/",
    "/aktuelles/",
    "pressemitteilung",
    "/rede-",
    "/webarchiv/",
)
_SOURCES_PER_TERM = 3
# A glossary page fits whole; of a long page (the Geschäftsordnung) the check
# reads the windows around the term. Generous: the check must see the rule it
# confirms, and it runs once per term.
_PASSAGE_CHARS = 16000
_WINDOW_CHARS = 700
_MIN_STEM = 6
_REDIRECT_TIMEOUT_S = 15

Fetch = Callable[[str], str]


class GlossarySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str


@dataclass(frozen=True)
class Research:
    # The search model's summary: what it found, not evidence.
    notes: str
    sources: list[GlossarySource]


@dataclass(frozen=True)
class SourcePassage:
    source: GlossarySource
    text: str


# (parliament name, term, the sentence it stood in) -> what the search found.
ResearchFn = Callable[[str, str, str], Awaitable[Research]]


def is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    return any(
        host == d or host.endswith(f".{d}") for d in ALLOWED_SOURCE_DOMAINS
    ) and not any(part in path for part in _EXCLUDED_PATH_PARTS)


def _resolve(uri: str) -> str:
    """Grounding links point at a Google redirect; the page is its target."""
    try:
        response = requests.get(
            uri, allow_redirects=False, timeout=_REDIRECT_TIMEOUT_S, stream=True
        )
        response.close()
    except requests.RequestException as exc:
        logger.info("Search result %s not resolved: %s", uri, exc)
        return uri
    return response.headers.get("Location") or uri


def allowed_sources(
    metadata: dict[str, Any], resolve: Callable[[str], str] = _resolve
) -> list[GlossarySource]:
    """The search results on an allowed domain, in the order found."""
    grounding = metadata.get("grounding_metadata") or {}
    found: dict[str, GlossarySource] = {}
    for chunk in grounding.get("grounding_chunks") or []:
        web = (chunk or {}).get("web") or {}
        uri = web.get("uri")
        if not uri:
            continue
        url = resolve(uri)
        if is_allowed(url) and url not in found:
            found[url] = GlossarySource(url=url, title=web.get("title") or url)
    return list(found.values())[:_SOURCES_PER_TERM]


async def grounded_research(parliament: str, term: str, context: str) -> Research:
    """Search the web for official explanations of ``term``. Tries the
    roster's Gemini models in turn; raises when none answered."""
    from ingestion.feed.publication_llms import search_llms  # noqa: PLC0415

    prompt = format_research_prompt(parliament, term, context)
    last: Optional[Exception] = None
    for llm in search_llms():
        try:
            searching = llm.model.bind_tools([{"google_search": {}}])
            message = await searching.ainvoke([HumanMessage(content=prompt)])
        except Exception as exc:  # noqa: BLE001 — the next model may answer
            logger.warning("Search for %r with %s failed: %s", term, llm.name, exc)
            last = exc
            continue
        sources = await asyncio.to_thread(allowed_sources, message.response_metadata)
        return Research(notes=message.text, sources=sources)
    raise last or RuntimeError("no Gemini model configured to search with")


class _PageText(HTMLParser):
    """A page's title and visible text, without scripts and page chrome."""

    _SKIP = frozenset({"script", "style", "noscript", "nav", "header", "footer"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._parts: list[str] = []
        self._skipping = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP:
            self._skipping += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skipping:
            self._skipping -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skipping:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._parts).split())


def page_text(html: str) -> tuple[str, str]:
    parser = _PageText()
    parser.feed(html)
    parser.close()
    return " ".join(parser.title.split()), parser.text


def _needles(terms: list[str]) -> list[str]:
    """What a page may call a term: each name of it, and the stem of each of
    their longer words ("Parlamentarische" for "Parlamentarischer",
    "Stellvertreter" for "Stellvertretendes")."""
    needles = {t.casefold() for t in terms}
    for term in terms:
        for word in term.split():
            if len(word) >= _MIN_STEM:
                needles.add(word[: max(_MIN_STEM, len(word) - 3)].casefold())
    return sorted(needles, key=len, reverse=True)


def passage(text: str, terms: list[str], limit: int = _PASSAGE_CHARS) -> str:
    """What the check reads of a page: all of it when short; else the
    windows around every mention of ``terms``, merged, up to ``limit``. One
    window around the first mention misses the rule a long page (the
    Geschäftsordnung) states further down."""
    if len(text) <= limit:
        return text
    folded = text.casefold()
    spans: list[tuple[int, int]] = []
    for needle in _needles(terms):
        at = folded.find(needle)
        while at != -1:
            spans.append((max(0, at - _WINDOW_CHARS), at + len(needle) + _WINDOW_CHARS))
            at = folded.find(needle, at + 1)
    if not spans:
        return text[:limit]
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    out: list[str] = []
    used = 0
    for start, end in merged:
        piece = text[start:end]
        if used + len(piece) > limit:
            piece = piece[: limit - used]
        out.append(piece)
        used += len(piece)
        if used >= limit:
            break
    return " … ".join(out)


def read_sources(
    sources: list[GlossarySource], terms: list[str], fetch: Fetch = fetch_page
) -> list[SourcePassage]:
    """The passage on the term, named by ``terms`` (its base form first, then
    its forms), of each source that could be read, titled as the page titles
    itself."""
    term = terms[0]
    read: list[SourcePassage] = []
    for source in sources:
        try:
            title, text = page_text(fetch(source.url))
        except Exception as exc:  # noqa: BLE001 — the other sources may do
            logger.warning("Source %s for %r not read: %s", source.url, term, exc)
            continue
        if not text:
            continue
        titled = source.model_copy(update={"title": title or source.title})
        read.append(SourcePassage(source=titled, text=passage(text, terms)))
    return read
