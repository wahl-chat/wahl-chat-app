# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Chat-facing PledgeTracker types.

The stored record lives in ``wahlchat_common.pledge_tracker`` because
ingestion writes it and this service reads it. ``PledgeTrackerSuggestions``
is only the inline chat payload, so it stays here.
"""

from pydantic import BaseModel

from wahlchat_common.pledge_tracker import PledgeRecord, PledgeTimelineEvent

__all__ = [
    "PledgeRecord",
    "PledgeTimelineEvent",
    "PledgeTrackerSuggestions",
]


class PledgeTrackerSuggestions(BaseModel):
    """Inline chat payload attached to one party_complete event."""

    party_id: str
    pledges: list[PledgeRecord]
