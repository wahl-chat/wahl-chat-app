# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Press coverage next to our own sources, behind a switch.

With ``GENERIC_CHAT_WEB_CONTEXT=on``, a vote or procedure a tool returns also
brings up to three web results about it: from our preferred outlets or a
Fraktion's own site, dated near its steps, and naming its subject. The model
sees them as tier "press". A party's position question may search the same
sites over the last months (web_search scope "statements").
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from typing import Iterable, Optional

from pydantic_ai.framing import wrap

from src.generic_chat import web_search as web
from src.generic_chat.schemas import (
    DebateResult,
    GenericChatDeps,
    NumberedDocument,
    ProcessResult,
    WebResult,
)
from wahlchat_common.answer_rules import PREFERRED_OUTLETS

logger = logging.getLogger(__name__)

ENV = "GENERIC_CHAT_WEB_CONTEXT"
FRAKTION_SITES: tuple[str, ...] = (
    "cducsu.de",
    "csu-landesgruppe.de",
    "spdfraktion.de",
    "gruene-bundestag.de",
    "linksfraktion.de",
    "afdbundestag.de",
)
# bundestag.de is the record our corpus already holds, not coverage of it.
STATEMENT_SITES = tuple(d for d in PREFERRED_OUTLETS if d != "bundestag.de") + FRAKTION_SITES
MAX_PRESS = 3
# Coverage that leads up to a law starts before its first step.
_BEFORE = timedelta(days=30)
_AFTER = timedelta(days=14)
STATEMENT_WINDOW = timedelta(days=90)
_GENERIC = frozenset(
    {
        "gesetz", "gesetzes", "gesetzentwurf", "entwurf", "eines", "änderung",
        "änderungen", "reform", "weiterer", "vorschriften", "bundestag",
        "antrag", "beschlussempfehlung", "fraktion", "zur", "über",
    }
)


def enabled() -> bool:
    return os.getenv(ENV, "off") == "on"


def _day(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def subject_words(title: str) -> list[str]:
    """Stems of the title's telling words: 'Nachrichtendienstrechts' → 'nachrich'."""
    words = re.findall(r"[\wäöüßÄÖÜ]{6,}", title.casefold())
    return sorted({w[:8] for w in words if w not in _GENERIC})


def _short_title(title: str) -> str:
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"^(Entwurf eines |Gesetzentwurf (der|zur) )", "", title, flags=re.I)
    return " ".join(title.split())[:120]


def matching(
    results: Iterable[WebResult], words: list[str], start: date, end: date
) -> list[WebResult]:
    """Dated inside the window and naming the subject; at most ``MAX_PRESS``."""
    out: list[WebResult] = []
    for result in results:
        day = _day(result.date)
        if day is None or not start <= day <= end:
            continue
        text = f"{result.title} {result.snippet}".casefold()
        if words and not any(w in text for w in words):
            continue
        out.append(result)
    return out[:MAX_PRESS]


def register(deps: GenericChatDeps, results: list[WebResult]) -> list[NumberedDocument]:
    documents = []
    for result in results:
        number = deps.sources.register(
            {
                "source": result.title,
                "page": 1,
                "document_publish_date": result.date,
                "url": result.url,
                "source_document": result.domain,
                "source_type": "web",
                "preferred_outlet": True,
            }
        )
        documents.append(
            NumberedDocument(
                id=number,
                source_type="web",
                title=result.title,
                date=result.date,
                outlet=result.domain,
                preferred_outlet=True,
                tier="press",
                text=wrap(web.WEB_SNIPPET_TAG, result.snippet),
            )
        )
    return documents


async def press_for(
    deps: GenericChatDeps, title: str, days: list[date]
) -> list[NumberedDocument]:
    """Coverage of one law or vote, once per chat turn."""
    if not enabled() or not title or not days or title in deps.press_seen:
        return []
    deps.press_seen.add(title)
    results, _ = await web.search_sites(f"{_short_title(title)} Bundestag", STATEMENT_SITES)
    found = matching(results, subject_words(title), min(days) - _BEFORE, max(days) + _AFTER)
    logger.info("web context: %d of %d results for %r", len(found), len(results), title[:60])
    return register(deps, found)


async def add_press(deps: GenericChatDeps, result: DebateResult | ProcessResult) -> None:
    """Append the coverage of what a tool returned to its documents."""
    if isinstance(result, ProcessResult):
        if result.procedure is None:
            return
        title = result.procedure.title
        days = [d for d in (_day(s.date) for s in result.steps) if d is not None]
    else:
        vote = next((d for d in result.documents if d.source_type == "vote_record"), None)
        item = result.item
        title = (vote.title if vote else None) or (item.headline if item else "") or ""
        days = [d for d in [_day(vote.date if vote else None), _day(item.date if item else None)] if d]
    result.documents = [*result.documents, *await press_for(deps, title, days)]


async def statements(deps: GenericChatDeps, query: str, today: date) -> list[NumberedDocument]:
    """web_search scope "statements": the preferred outlets and the Fraktionen's
    own sites over the last months."""
    results, _ = await web.search_sites(query, STATEMENT_SITES, recency="year")
    found = matching(results, [], today - STATEMENT_WINDOW, today)
    return register(deps, found)
