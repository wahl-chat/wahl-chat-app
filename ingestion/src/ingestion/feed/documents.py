# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The Drucksachen behind a debate and a vote, as ``"{wp}/{number}"``.

A shared Drucksache is the one exact link between an agenda item and a poll:
the protocol lists the documents an agenda item deals with, and
abgeordnetenwatch links the documents a poll was about. Topics are too broad
for it: two health debates a week apart share a topic, not a vote.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Optional

from ingestion.drucksache_numbers import drucksachen_in_links, drucksachen_in_text

__all__ = [
    "PollDocuments",
    "drucksachen_in_links",
    "drucksachen_in_text",
    "poll_documents",
]

logger = logging.getLogger(__name__)

PollDocuments = Callable[[int], Optional[list[str]]]


def poll_documents(client: Any) -> PollDocuments:
    """Look up a poll's Drucksachen on abgeordnetenwatch, which links them in
    the poll's intro; the corpus keeps that intro as plain text only.

    None when the lookup fails, so the item keeps no answer and a later run
    asks again; an empty list is an answer (the poll links no Drucksache).
    """

    def lookup(poll_id: int) -> Optional[list[str]]:
        try:
            poll = client.get(f"polls/{int(poll_id)}")["data"]
        except Exception as exc:  # noqa: BLE001 — retried next run
            logger.warning("No Drucksachen for poll %s: %s", poll_id, exc)
            return None
        return drucksachen_in_links(str(poll.get("field_intro") or ""))

    return lookup
