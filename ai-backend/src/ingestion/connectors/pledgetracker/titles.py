# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Short-headline generation for pledge timeline events.

Timeline events arrive as full sentences ("Der gesetzliche Mindestlohn wurde im
Januar 2026 auf 13,90 Euro pro Stunde angehoben."), which read as walls of text
on a phone. This module generates one compact German headline per event
(``event_short``) in a single batched LLM call per pledge, using the shared
pre/post-processing failover roster.

Failure policy is strict but soft: any LLM problem (error, count mismatch,
missing key) leaves ``event_short`` as None and never fails ingestion — the UI
falls back to the full event text.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional

from langchain_core.messages import BaseMessage, HumanMessage

from src.models.pledge_tracker import PledgeRecord
from src.models.structured_outputs import PledgeEventHeadlines

logger = logging.getLogger(__name__)

_MAX_WORDS = 8

_PROMPT_TEMPLATE = """\
Du fasst Ereignisse aus der Zeitleiste eines politischen Ziels in sehr kurze \
deutsche Schlagzeilen zusammen.

Politisches Ziel: {claim}

Erstelle für jedes der folgenden Ereignisse genau EINE Schlagzeile mit höchstens \
{max_words} Wörtern. Gib die Schlagzeilen in derselben Reihenfolge zurück wie die \
Ereignisse. Wichtig: Nur den Inhalt des Ereignisses zusammenfassen — KEINE \
Bewertung, ob das Ziel erfüllt oder gebrochen wurde.

Ereignisse:
{events}
"""

# Injectable for tests; the default resolves lazily so importing this module
# never touches LLM configuration.
_StructuredOutputFn = Callable[[list[BaseMessage]], Coroutine[Any, Any, Any]]


async def _default_structured_output(messages: list[BaseMessage]) -> Any:
    from src.llms import (  # noqa: PLC0415
        PRE_AND_POST_PROCESSING_LLMS,
        get_structured_output_from_llms,
    )

    return await get_structured_output_from_llms(
        PRE_AND_POST_PROCESSING_LLMS, messages, PledgeEventHeadlines
    )


def add_short_titles(
    record: PledgeRecord,
    *,
    _structured_output_fn: Optional[_StructuredOutputFn] = None,
) -> int:
    """Fill ``event_short`` on the record's events that are missing it.

    One batched call per pledge. Returns the number of titles added (0 on any
    failure — ingestion and backfill always proceed).
    """
    pending = [e for e in record.timeline_events if not e.event_short and e.event]
    if not pending:
        return 0

    events_block = "\n".join(f"{i + 1}. {e.event}" for i, e in enumerate(pending))
    prompt = _PROMPT_TEMPLATE.format(
        claim=record.claim,
        max_words=_MAX_WORDS,
        events=events_block,
    )
    fn = _structured_output_fn or _default_structured_output

    try:
        result: Any = asyncio.run(fn([HumanMessage(content=prompt)]))
        headlines = list(result.headlines)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Short-title generation failed for pledge %s: %s",
            record.pledge_id,
            exc,
        )
        return 0

    if len(headlines) != len(pending):
        logger.warning(
            "Short-title count mismatch for pledge %s (%d events, %d headlines) — "
            "keeping full texts",
            record.pledge_id,
            len(pending),
            len(headlines),
        )
        return 0

    added = 0
    for event, headline in zip(pending, headlines):
        cleaned = str(headline).strip()
        if cleaned:
            event.event_short = cleaned
            added += 1
    return added
