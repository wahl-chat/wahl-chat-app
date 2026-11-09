# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Feed item identity, input hashes and the edition that lists a day's items.

The source defines the structure: one agenda item of a sitting is one debate
item, one poll is one vote item. Both ids come from the source, never from a
model, so a rebuilt item keeps its id and every link and ``feed_interest`` row
pointing at it stays valid. Each item carries the hash of its own inputs, so a
late speech regenerates its own debate and nothing else.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Literal, Optional

from ingestion.feed.models import (
    CANONICAL_LOCALE,
    DigestProtocol,
    FeedEdition,
    FeedItem,
    LocalizedContent,
    LocalizedPosition,
)
from ingestion.feed.parliaments import Parliament
from ingestion.feed.prompts import PROMPT_VERSION
from ingestion.feed.reader import AgendaItem

# Items stored before the input hash covered sources only also hashed these
# two versions. Their hashes are recomputed with the last values, so those
# items count as current instead of being regenerated.
_LEGACY_HASH_VERSIONS = {"prompt": "10", "format": "3"}

_HASHED_FIELDS = (
    "headline",
    "teaser",
    "key_points",
    "positions",
    "suggested_questions",
    "quote_translation",
)


# Runs that may try a Fraktion's position before the debate is listed without
# one for good. A sentence the check keeps rejecting (remarks from the chair
# filed under a party, say) would otherwise be retried for as long as the item
# stays in the window.
MAX_POSITION_ATTEMPTS = 3

BuildNeed = Literal["full", "positions"]


def build_needed(
    stored: Optional[FeedItem],
    input_hash: str,
    legacy_input_hash: Optional[str] = None,
) -> Optional[BuildNeed]:
    """What an item needs this run: a full build, another attempt at only its
    missing positions, or nothing. The feed builder and the backfill plan
    both decide with this, so a plan's "to build" is what a run would do.

    Only a change of the item's sources makes it "full". A new prompt or a new
    stored shape does not: a prompt change is rebuilt on purpose (``--force``),
    a shape change is a migration over the stored items."""
    if (
        stored is None
        or stored.status != "published"
        # None marks a vote whose texts fell back: it is always retried.
        or stored.input_hash is None
        or stored.input_hash not in (input_hash, legacy_input_hash)
    ):
        return "full"
    if stored.pending_positions and stored.position_attempts < MAX_POSITION_ATTEMPTS:
        return "positions"
    return None


def vote_item_id(edition_id: str, poll_id: int) -> str:
    return f"{edition_id}_v{poll_id}"


def debate_item_id(edition_id: str, session: int, agenda_slug: str) -> str:
    """The session number and the agenda slug ("top20", "zp5") from the
    protocol: a day can hold two sittings, each with its own TOP 1."""
    return f"{edition_id}_d{session}-{agenda_slug}"


def _input_hash(
    sources: list[str], label: Optional[str] = None, *, legacy: bool = False
) -> str:
    payload: dict[str, object] = {"sources": sorted(sources)}
    if legacy:
        payload |= _LEGACY_HASH_VERSIONS
    if label is not None:
        payload["label"] = label
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def debate_input_hash(item: AgendaItem, *, legacy: bool = False) -> str:
    """Over the speeches' chunk hashes, not their order: a debate is built
    only once the protocol has put it in order, and that order is fixed. The
    label is in it because it reaches the prompt and the card, and a protocol
    published after the first build can still give the item its title."""
    return _input_hash(
        [h for s in item.speeches for h in s.content_hashes],
        label=item.label,
        legacy=legacy,
    )


def vote_input_hash(payload: dict, *, legacy: bool = False) -> str:
    return _input_hash([str(payload.get("content_hash") or "")], legacy=legacy)


def content_hash(content: LocalizedContent) -> str:
    """Hash of the reader-facing text only, not of its provenance."""
    payload = content.model_dump(mode="json", include=set(_HASHED_FIELDS))
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def canonical_content(
    *,
    headline: str,
    teaser: Optional[str],
    key_points: list[str],
    positions: list[LocalizedPosition],
    suggested_questions: list[str],
    generated_by: Optional[str],
    generated_at: datetime,
) -> dict[str, LocalizedContent]:
    content = LocalizedContent(
        headline=headline,
        teaser=teaser or None,
        key_points=key_points,
        positions=positions,
        suggested_questions=suggested_questions,
        origin="generated",
        source_hash="",
        prompt_version=PROMPT_VERSION,
        generated_by=generated_by,
        generated_at=generated_at,
    )
    content.source_hash = content_hash(content)
    return {CANONICAL_LOCALE: content}


def assemble_edition(
    parliament: Parliament,
    edition_id: str,
    day: date,
    protocols: list[DigestProtocol],
    items: list[FeedItem],
    generated_at: datetime,
) -> tuple[FeedEdition, list[FeedItem]]:
    """The edition listing ``items`` in their given order, and the items with
    their rank set to that order. Items whose rank changes are returned as
    copies, so the stored version is never mutated."""
    ranked: list[FeedItem] = []
    for rank, item in enumerate(items):
        ranked.append(
            item if item.rank == rank else item.model_copy(update={"rank": rank})
        )
    edition = FeedEdition(
        id=edition_id,
        parliament=parliament.id,
        parliament_name=parliament.name,
        region=parliament.region,
        date=day,
        protocols=protocols,
        item_ids=[i.id for i in ranked],
        generated_at=generated_at,
    )
    return edition, ranked
