# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Check every position sentence against what its Fraktion actually said.

The structural checks (the party spoke, the quote is verbatim) cannot catch
a sentence that sharpens "asks for a review" into "demands abolition", and a
wrong position published under a party's name is the most damaging mistake
the feed can make. So a second call reads each sentence next to that
Fraktion's own speeches, and only a sentence it confirms is published. A
check that fails raises, and the caller publishes nothing of the debate in
that run: an unchecked sentence is never shown, and neither is a debate
whose positions are missing only because a call failed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ingestion.feed.prompts import PositionCheckBatch, format_verify_prompt
from ingestion.feed.reader import Speech

if TYPE_CHECKING:
    from ingestion.feed.builder import FeedBuilder

logger = logging.getLogger(__name__)


def _speeches_by_party_block(
    positions: dict[str, str], by_party: dict[str, list[Speech]]
) -> str:
    from ingestion.feed.builder import speeches_block  # noqa: PLC0415

    return "\n\n".join(
        f"## {party_id}\n{speeches_block(by_party.get(party_id, []))}"
        for party_id in positions
    )


async def verify_positions(
    builder: FeedBuilder,
    parliament_name: str,
    agenda_label: str,
    positions: dict[str, str],
    by_party: dict[str, list[Speech]],
) -> dict[str, str]:
    """The subset of ``positions`` (Fraktion -> sentence) the speeches support.

    Raises when the check itself fails, so "not checked" never reads as
    "rejected".
    """
    if not positions:
        return {}
    refs = {f"P{i + 1}": party_id for i, party_id in enumerate(positions)}
    lines = "\n".join(
        f"[{ref}] {party_id}: {positions[party_id]}" for ref, party_id in refs.items()
    )
    result, _ = await builder.acall(
        format_verify_prompt(
            parliament_name,
            agenda_label,
            lines,
            _speeches_by_party_block(positions, by_party),
        ),
        PositionCheckBatch,
    )
    supported: dict[str, str] = {}
    for check in result.checks:
        party_id = refs.get(check.ref.strip())
        if party_id is None:
            continue
        if check.supported:
            supported[party_id] = positions[party_id]
        else:
            logger.info(
                "Position of %s on %r not supported: %s",
                party_id,
                agenda_label,
                check.reason,
            )
    return supported
