# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""PledgeTracker suggestion retrieval for chat answers.

Flow per party answer: Qdrant search hard-filtered by source_type=pledge_record,
party_id (tenant) and region ∈ context.region_path → an LLM relevance gate →
Firestore hydration of the surviving pledge ids → PledgeTrackerSuggestions
attached to the party_complete event.

The gate exists because top-k nearest-neighbor ranks but never judges: with few
pledges per party the top 3 always include weak matches (observed: rank 1 at
cosine ~0.68, ranks 2-3 in a ~0.30-0.36 noise floor). Dropping all candidates is
a valid outcome — the UI then shows no PledgeTracker entry point at all.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, cast

from langchain_core.messages import BaseMessage, HumanMessage

from src.firebase_service import aget_context_by_id, aget_pledges_by_ids
from src.ingestion.retrieve import retrieve
from src.models.pledge_tracker import PledgeTrackerSuggestions
from src.models.structured_outputs import PledgeRelevanceOutput

logger = logging.getLogger(__name__)

_GATE_TIMEOUT_S = 8.0

_RELEVANCE_PROMPT = """\
Du prüfst, welche politischen Ziele thematisch zu einer Nutzerfrage passen.

Nutzerthema: {query}

Kandidaten:
{candidates}

Gib die Nummern der Kandidaten zurück, die KLAR dasselbe Thema behandeln wie das \
Nutzerthema. Im Zweifel einen Kandidaten NICHT aufnehmen. Es geht nur um die \
thematische Passung — nicht darum, ob ein Ziel erfüllt wurde. Wenn kein Kandidat \
passt, gib eine leere Liste zurück.
"""

# Injectable for tests; the default resolves lazily so importing this module
# never touches LLM configuration.
_StructuredOutputFn = Callable[[list[BaseMessage]], Awaitable[Any]]


async def _default_structured_output(messages: list[BaseMessage]) -> Any:
    from src.llms import (  # noqa: PLC0415
        PRE_AND_POST_PROCESSING_LLMS,
        get_structured_output_from_llms,
    )

    return await get_structured_output_from_llms(
        PRE_AND_POST_PROCESSING_LLMS, messages, PledgeRelevanceOutput
    )


async def _afilter_relevant_payloads(
    query: str,
    payloads: list[dict],
    *,
    _structured_output_fn: Optional[_StructuredOutputFn] = None,
) -> list[dict]:
    """Keep only candidates the gate judges on-topic for ``query``.

    Failure policy: any LLM error, timeout, or invalid output returns ALL
    candidates — the pre-gate behavior — so the gate can only improve
    precision, never hide data because of an outage.
    """
    if not payloads:
        return payloads

    candidates_block = "\n\n".join(
        f"{i + 1}.\n{payload.get('text') or payload.get('citation_title') or ''}"
        for i, payload in enumerate(payloads)
    )
    prompt = _RELEVANCE_PROMPT.format(query=query, candidates=candidates_block)
    fn = _structured_output_fn or _default_structured_output

    try:
        result = await asyncio.wait_for(
            fn([HumanMessage(content=prompt)]), timeout=_GATE_TIMEOUT_S
        )
        indices = list(result.relevant_indices)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Pledge relevance gate failed — keeping all %d candidates: %s",
            len(payloads),
            exc,
        )
        return payloads

    if not all(isinstance(i, int) and 1 <= i <= len(payloads) for i in indices):
        logger.warning(
            "Pledge relevance gate returned invalid indices %r for %d candidates "
            "— keeping all",
            indices,
            len(payloads),
        )
        return payloads

    # Dedupe while preserving the retrieval (similarity) order.
    kept_positions = sorted({i - 1 for i in indices})
    logger.info(
        "Pledge relevance gate kept %d of %d candidates",
        len(kept_positions),
        len(payloads),
    )
    return [payloads[i] for i in kept_positions]


async def aretrieve_pledge_tracker_suggestions(
    *,
    query: str,
    party_id: str,
    context_id: str,
    query_vector: Optional[list[float]] = None,
    limit: int = 3,
) -> Optional[PledgeTrackerSuggestions]:
    """Retrieve gated pledge suggestions for one party answer, or None."""
    context = await aget_context_by_id(context_id)
    region_path = context.region_path if context and context.region_path else ["DE"]

    payloads = cast(
        list[dict],
        await asyncio.to_thread(
            retrieve,
            query,
            source_type="pledge_record",
            party_id=party_id,
            region_path=region_path,
            limit=limit,
            query_vector=query_vector,
        ),
    )

    payloads = await _afilter_relevant_payloads(query, payloads)

    pledge_ids: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        pledge_id = payload.get("pledge_id")
        if isinstance(pledge_id, str) and pledge_id not in seen:
            seen.add(pledge_id)
            pledge_ids.append(pledge_id)

    if not pledge_ids:
        return None

    pledges = await aget_pledges_by_ids(pledge_ids[:limit])
    if not pledges:
        return None

    return PledgeTrackerSuggestions(party_id=party_id, pledges=pledges[:limit])
