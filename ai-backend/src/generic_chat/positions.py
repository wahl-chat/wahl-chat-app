# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Each party's reasons on one law, in tiers.

What a party said and tabled in the same procedure comes first: its speeches
in the readings, its own amendments and resolutions, and the committee
report's passage on it. Its wider record on the topic (other speeches, the
manifesto) follows as context. The vote's own debate, the first tier, comes
with get_vote.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

from qdrant_client.models import DatetimeRange

from src.generic_chat import tools
from src.generic_chat.schemas import GenericChatDeps, NumberedDocument, Tier
from src.models.context import ContextParty
from src.retrieve import retrieve
from src.services import procedure_service

logger = logging.getLogger(__name__)

# Per party: (speeches, own motions, report passages, context) with up to two
# parties asked about, and leaner with more, so all of them fit.
_FULL = (3, 2, 2, 2)
_LEAN = (2, 1, 1, 1)
_SPEECH_CHARS = 1200
_REPORT_CANDIDATES = 12
_CONTEXT_YEARS = 2


def _names(party: ContextParty) -> re.Pattern[str]:
    """How a committee report names the Fraktion: "Fraktion der SPD",
    "BÜNDNIS 90/DIE GRÜNEN", "Die Linke"."""
    forms = {party.name, party.long_name or party.name}
    if party.party_id == "gruene":
        forms.add("GRÜNEN")
    return re.compile("|".join(re.escape(f) for f in forms if f), re.IGNORECASE)


def _key(payload: dict) -> str:
    return str(payload.get("speech_key") or payload.get("source_item_id") or payload.get("chunk_key"))


async def _speeches(vorgang_id: str, party_id: str, cap: int) -> list[dict]:
    view = await procedure_service.aget_procedure_view(vorgang_id, party_id=party_id, limit=60)
    if view is None:
        return []
    seen: set[str] = set()
    picked: list[dict] = []
    # Newest first: the reading closest to the vote says most about it.
    for payload in sorted(view.speeches, key=lambda p: str(p.get("publish_date") or ""), reverse=True):
        if _key(payload) not in seen:
            seen.add(_key(payload))
            picked.append(payload)
    return picked[:cap]


async def _motions(vorgang_id: str, party_id: str, query: str, cap: int) -> list[dict]:
    """The overview of Drucksachen the party tabled in the procedure."""
    hits = await _payloads(
        query, source_type="drucksache", vorgang_id=vorgang_id, party_id=party_id,
        doc_section=["overview"], limit=cap * 3,
    )
    by_document: dict[str, dict] = {}
    for payload in hits:
        by_document.setdefault(str(payload.get("source_parent_key")), payload)
    return list(by_document.values())[:cap]


async def _report(vorgang_id: str, party: ContextParty, query: str, cap: int) -> list[dict]:
    """Committee report passages that name the Fraktion. Report chunks carry
    no party, so the name decides."""
    hits = await _payloads(
        f"{query} Fraktion {party.name}", source_type="drucksache", vorgang_id=vorgang_id,
        doc_section=["report"], limit=_REPORT_CANDIDATES,
    )
    names = _names(party)
    return [p for p in hits if names.search(str(p.get("text") or ""))][:cap]


async def _context(
    party_id: str, query: str, scope: set[str], region_path: list[str], level: Optional[str], cap: int
) -> list[dict]:
    """The party's recent speeches on the topic outside the procedure, then
    its manifesto."""
    since = datetime.now(timezone.utc) - timedelta(days=365 * _CONTEXT_YEARS)
    speeches, manifesto = await asyncio.gather(
        _payloads(
            query, source_type="parliamentary_speech", party_id=party_id,
            region_path=region_path, level=level, limit=cap + 6,
            publish_range=DatetimeRange(gte=since),
        ),
        _payloads(
            query, source_type="party_manifesto", party_id=party_id,
            region_path=region_path, level=level, limit=1,
        ),
    )
    outside = [
        p for p in speeches
        if not scope & {str(v) for v in p.get("vorgang_ids") or []}
    ]
    return [*outside[: max(cap - 1, 1)], *manifesto][:cap]


async def _payloads(query: str, **filters: Any) -> list[dict]:
    return cast(list[dict], await retrieve(query, **filters))


def _tagged(doc: NumberedDocument, tier: Tier) -> NumberedDocument:
    return doc.model_copy(update={"tier": tier})


_Fetched = tuple[list[dict], list[dict], list[dict], list[dict]]


async def _fetch_party(
    deps: GenericChatDeps,
    party: ContextParty,
    vorgang_ids: list[str],
    query: str,
    caps: tuple[int, int, int, int],
    skip: set[str],
) -> _Fetched:
    n_speeches, n_motions, n_report, n_context = caps
    law = vorgang_ids[0]
    results = await asyncio.gather(
        _speeches(law, party.party_id, n_speeches + len(skip)),
        _motions(law, party.party_id, query, n_motions),
        _report(law, party, query, n_report),
        _context(
            party.party_id, query, set(vorgang_ids), deps.context.region_path,
            deps.context.level, n_context,
        ),
        return_exceptions=True,
    )
    for part, result in zip(("speeches", "motions", "report", "context"), results):
        if isinstance(result, BaseException):
            logger.warning("positions: %s for %s failed: %s", part, party.party_id, result)
    speeches, motions, report, context = (
        [] if isinstance(r, BaseException) else r for r in results
    )
    fresh = [p for p in speeches if str(p.get("citation_title")) not in skip][:n_speeches]
    return fresh, motions, report, context


def _register_party(deps: GenericChatDeps, fetched: _Fetched, query: str) -> list[NumberedDocument]:
    from src.generic_chat.process import _register_document  # noqa: PLC0415 (process imports tools)

    speeches, motions, report, context = fetched
    out = [
        _tagged(tools._register_speech(deps, p, query, tools._clip(p.get("text"), _SPEECH_CHARS)), "this_procedure")
        for p in speeches
    ]
    out += [_tagged(_register_document(deps, p), "this_procedure") for p in [*motions, *report]]
    out += [_tagged(tools._register_payload(deps, p, query), "context") for p in context]
    return out


async def party_positions(
    deps: GenericChatDeps,
    vorgang_ids: list[str],
    party_ids: list[str],
    query: str,
    skip: Optional[set[str]] = None,
) -> list[NumberedDocument]:
    """Per party asked about, in the order asked: its statements and motions
    in the procedure, then a little of its wider record. ``skip`` holds the
    titles of speeches already shown."""
    by_id = {p.party_id: p for p in deps.parties}
    parties = [by_id[pid] for pid in dict.fromkeys(party_ids) if pid in by_id]
    if not vorgang_ids or not parties:
        return []
    caps = _FULL if len(parties) <= 2 else _LEAN
    fetched = await asyncio.gather(
        *(_fetch_party(deps, party, vorgang_ids, query, caps, skip or set()) for party in parties)
    )
    # Numbered in the order asked, so the same question gets the same numbers.
    bundles = [_register_party(deps, f, query) for f in fetched]
    # A report passage can name several Fraktionen: show it once.
    seen: set[int] = set()
    out: list[NumberedDocument] = []
    for doc in (doc for bundle in bundles for doc in bundle):
        if doc.id not in seen:
            seen.add(doc.id)
            out.append(doc)
    return out

