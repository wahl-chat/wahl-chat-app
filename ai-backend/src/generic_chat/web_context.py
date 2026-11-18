# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Press coverage of a procedure, next to our own sources.

A procedure get_process returns also brings up to three web results about
it: from our preferred news outlets or a Fraktion's own site, dated near its
steps, and naming its subject. The model sees them as tier "press", for
what led to a law and how it was received. Votes and party positions get
none: in the blind eval it helped only with "why now" questions.
``GENERIC_CHAT_WEB_CONTEXT=off`` turns it off.
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
PRESS_SITES = tuple(d for d in PREFERRED_OUTLETS if d != "bundestag.de") + FRAKTION_SITES
MAX_PRESS = 3
# Coverage that leads up to a law starts before its first step.
_BEFORE = timedelta(days=30)
_AFTER = timedelta(days=14)
_GENERIC = frozenset(
    {
        "gesetz", "gesetzes", "gesetzentwurf", "entwurf", "eines", "änderung",
        "änderungen", "reform", "weiterer", "vorschriften", "bundestag",
        "antrag", "beschlussempfehlung", "fraktion", "zur", "über",
    }
)


def enabled() -> bool:
    return os.getenv(ENV, "on") != "off"


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


def _register(deps: GenericChatDeps, results: list[WebResult]) -> list[NumberedDocument]:
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


async def add_press(deps: GenericChatDeps, result: ProcessResult) -> None:
    """Append the procedure's coverage to its documents, once per turn. A
    feed button's answer is cached, so it stands on our data alone."""
    procedure = result.procedure
    if not enabled() or procedure is None or deps.preset is not None:
        return
    if procedure.vorgang_id in deps.press_seen:
        return
    deps.press_seen.add(procedure.vorgang_id)
    days = [d for d in (_day(s.date) for s in result.steps) if d is not None]
    if not days:
        return
    results, _ = await web.search_sites(f"{_short_title(procedure.title)} Bundestag", PRESS_SITES)
    found = matching(
        results, subject_words(procedure.title), min(days) - _BEFORE, max(days) + _AFTER
    )
    logger.info(
        "press: %d of %d results for procedure %s", len(found), len(results), procedure.vorgang_id
    )
    result.documents = [*result.documents, *_register(deps, found)]
