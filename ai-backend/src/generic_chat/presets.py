# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Answers to the feed's fixed questions.

Every reader of an item asks a button's question with the same anchor, so the
answer is cached. The key holds the rendered prompt, whose anchor block carries
the documents the answer stands on: new data on the item (a protocol, a step,
a Drucksache) changes the key. Web search is off for these turns (see
``agent._within_budget``), so the key covers what the answer may draw on; the
age limit catches what a later tool call found.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.generic_chat.prompt import build_system_prompt
from src.generic_chat.schemas import GenericChatDeps
from src.services.firebase_service import async_db

logger = logging.getLogger(__name__)

_COLLECTION = "cached_chat_answers"
_MAX_AGE = timedelta(days=7)
# The key ignores the day, so an answer lives across days.
_KEY_DAY = date(2000, 1, 1)
# Bump when the cached shape or the way answers are made changes.
_VERSION = "1"


class CachedTurn(BaseModel):
    answer: str
    sources: list[dict]
    quick_replies: list[str] = Field(default_factory=list)
    title: str = ""
    created_at: datetime


def cache_key(deps: GenericChatDeps, question: str, model: Any) -> str:
    model_name = str(getattr(model, "model_name", None) or type(model).__name__)
    parts = [
        _VERSION,
        model_name,
        deps.preset or "",
        deps.context.context_id,
        deps.language,
        question.strip(),
        build_system_prompt(deps, today=_KEY_DAY),
    ]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


async def aload(key: str) -> Optional[CachedTurn]:
    try:
        snap = await async_db.collection(_COLLECTION).document(key).get()
        if not snap.exists:
            return None
        turn = CachedTurn.model_validate(snap.to_dict() or {})
    except Exception as exc:  # noqa: BLE001 (a cache miss, never an error)
        logger.warning("preset cache read failed: %s", exc)
        return None
    if datetime.now(timezone.utc) - turn.created_at > _MAX_AGE:
        return None
    return turn


async def astore(key: str, turn: CachedTurn) -> None:
    try:
        await async_db.collection(_COLLECTION).document(key).set(turn.model_dump())
    except Exception as exc:  # noqa: BLE001 (the answer was already sent)
        logger.warning("preset cache write failed: %s", exc)
