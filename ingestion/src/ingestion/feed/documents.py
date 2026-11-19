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
import re
from collections.abc import Callable, Iterable
from typing import Any, Optional

logger = logging.getLogger(__name__)

# "21/6130" as the protocol prints it.
_DRUCKSACHE_TEXT = re.compile(r"\b(\d{2})/(\d{1,5})\b")
# The PDF of Drucksache 21/6130: dserver.bundestag.de/btd/21/061/2106130.pdf
_DRUCKSACHE_PDF = re.compile(
    r"dserver\.bundestag\.de/btd/(\d{2})/\d{3}/(\d{2})(\d{5})\.pdf"
)

PollDocuments = Callable[[int], Optional[list[str]]]


def _sorted(ids: Iterable[tuple[int, int]]) -> list[str]:
    return [f"{wp}/{number}" for wp, number in sorted(set(ids))]


def drucksachen_in_text(text: str) -> list[str]:
    return _sorted(
        (int(wp), int(number)) for wp, number in _DRUCKSACHE_TEXT.findall(text)
    )


def drucksachen_in_links(html: str) -> list[str]:
    """The Drucksachen an HTML text links to, by their PDF on dserver."""
    return _sorted(
        (int(wp), int(number))
        for wp, file_wp, number in _DRUCKSACHE_PDF.findall(html)
        if wp == file_wp
    )


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
