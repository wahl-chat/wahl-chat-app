# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Split a built ``DailyDigest`` into its published edition and feed items.

Pure and free of LLM calls: the builder's output and a ``daily_digests`` doc
stored before the split go through the same function, so existing days move
to the item shape without being generated again.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from ingestion.feed.models import (
    CANONICAL_LOCALE,
    DailyDigest,
    DebateFacts,
    DebateParty,
    DigestSessionSection,
    DigestVote,
    FeedEdition,
    FeedItem,
    LocalizedContent,
    LocalizedPosition,
    VoteFacts,
)
from ingestion.feed.prompts import PROMPT_VERSION

_HASHED_FIELDS = (
    "headline",
    "teaser",
    "key_points",
    "positions",
    "suggested_questions",
    "quote_translation",
)


def vote_item_id(edition_id: str, poll_id: int) -> str:
    return f"{edition_id}_v{poll_id}"


def debate_item_id(edition_id: str, agenda_items: list[str]) -> str:
    """Keyed by the debate's official agenda labels, which come from the
    source: a rebuilt day yields the same id for the same debate, where a
    position in the list would shift whenever the model reorders sections."""
    digest = hashlib.sha256("\n".join(sorted(agenda_items)).encode("utf-8"))
    return f"{edition_id}_d{digest.hexdigest()[:8]}"


def content_hash(content: LocalizedContent) -> str:
    """Hash of the reader-facing text only, not of its provenance."""
    payload = content.model_dump(mode="json", include=set(_HASHED_FIELDS))
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _canonical(
    *,
    headline: str,
    teaser: Optional[str],
    key_points: list[str],
    positions: list[LocalizedPosition],
    suggested_questions: list[str],
    generated_by: Optional[str],
    generated_at: datetime,
) -> LocalizedContent:
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
    return content


def _debate_item(
    digest: DailyDigest,
    section: DigestSessionSection,
    item_id: str,
    index: int,
    rank: int,
    generated_by: Optional[str],
) -> FeedItem:
    assert digest.session is not None
    return FeedItem(
        id=item_id,
        kind="debate",
        edition_id=digest.id,
        parliament=digest.parliament,
        parliament_name=digest.parliament_name,
        region=digest.region,
        date=digest.date,
        rank=rank,
        topics=section.topics or [section.topic],
        debate=DebateFacts(
            protocols=digest.session.protocols,
            agenda_items=section.agenda_items,
            citations=section.citations,
            parties=[
                DebateParty(
                    party_id=p.party_id,
                    party_name=p.party_name,
                    color=p.color,
                    speakers=p.speakers,
                )
                for p in section.positions
            ],
            video_url=section.video_url,
            heat=section.heat,
            debate_minutes=section.debate_minutes,
            opened_by=section.opened_by,
            opening_quote=section.opening_quote,
        ),
        content={
            CANONICAL_LOCALE: _canonical(
                headline=section.headline,
                teaser=section.summary,
                key_points=section.key_points,
                positions=[
                    LocalizedPosition(party_id=p.party_id, text=p.position)
                    for p in section.positions
                ],
                suggested_questions=section.suggested_questions,
                generated_by=generated_by,
                generated_at=digest.generated_at,
            )
        },
        legacy_keys=[f"{digest.id}~s{index}"],
        input_hash=digest.input_hash,
        generated_at=digest.generated_at,
    )


def _vote_item(digest: DailyDigest, vote: DigestVote, rank: int) -> FeedItem:
    return FeedItem(
        id=vote_item_id(digest.id, vote.poll_id),
        kind="vote",
        edition_id=digest.id,
        parliament=digest.parliament,
        parliament_name=digest.parliament_name,
        region=digest.region,
        date=digest.date,
        rank=rank,
        topics=vote.topics,
        vote=VoteFacts(
            poll_id=vote.poll_id,
            official_title=vote.title,
            outcome=vote.outcome,
            citation_url=vote.citation_url,
            description=vote.description,
            parties=vote.parties,
        ),
        content={
            CANONICAL_LOCALE: _canonical(
                headline=vote.short_title,
                teaser=vote.summary,
                key_points=[],
                positions=[],
                suggested_questions=vote.suggested_questions,
                generated_by=vote.generated_by,
                generated_at=digest.generated_at,
            )
        },
        legacy_keys=[f"{digest.id}~v{vote.poll_id}"],
        input_hash=digest.input_hash,
        generated_at=digest.generated_at,
    )


def _unique(item_id: str, taken: set[str]) -> str:
    # Two sections on the same agenda items would be a model error, but must
    # not overwrite each other.
    candidate, n = item_id, 2
    while candidate in taken:
        candidate, n = f"{item_id}-{n}", n + 1
    taken.add(candidate)
    return candidate


def split_digest(digest: DailyDigest) -> tuple[FeedEdition, list[FeedItem]]:
    items: list[FeedItem] = []
    taken: set[str] = set()
    session = digest.session
    for index, section in enumerate(session.sections if session else []):
        item_id = _unique(debate_item_id(digest.id, section.agenda_items), taken)
        items.append(
            _debate_item(
                digest,
                section,
                item_id,
                index,
                rank=len(items),
                generated_by=session.generated_by if session else None,
            )
        )
    for vote in digest.votes:
        items.append(_vote_item(digest, vote, rank=len(items)))

    edition = FeedEdition(
        id=digest.id,
        parliament=digest.parliament,
        parliament_name=digest.parliament_name,
        region=digest.region,
        date=digest.date,
        protocols=session.protocols if session else [],
        item_ids=[item.id for item in items],
        other_topics=session.other_topics if session else [],
        input_hash=digest.input_hash,
        generated_at=digest.generated_at,
    )
    return edition, items
