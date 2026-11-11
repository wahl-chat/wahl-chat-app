# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Which speech a debate card plays, and from which second.

Chosen once, here, from the item's facts, because two consumers must agree on
it: the poster is cut at that second (``posters.py``) and the web player opens
at it. Were the web to choose again, a changed rule on either side would show
one frame and play another.
"""

from __future__ import annotations

from typing import Optional

from ingestion.feed.models import CardVideo, DebateFacts

# The first frames of a file are often black; a still from second zero would
# be an empty card.
MIN_START = 0.5


def _start(link: Optional[str]) -> float:
    """The second a ``…#t=83.5`` link opens at, never before ``MIN_START``."""
    try:
        start = float((link or "").split("#t=")[1])
    except (IndexError, ValueError):
        return MIN_START
    return start if start > MIN_START else MIN_START


def _bare(url: str) -> str:
    return url.split("#")[0]


def choose_card_video(debate: DebateFacts) -> Optional[CardVideo]:
    """The opening speaker's speech when known, since the opening quote is
    theirs; otherwise the first speech with video of the Fraktion that spoke
    first (``parties`` is stored in order of first speech), then any cited
    speech video, then the agenda item's first video."""
    speakers = [
        CardVideo(
            video_url=_bare(speaker.video_url),
            start=_start(speaker.video_link),
            speaker=speaker.name,
            party_name=party.party_name,
        )
        for party in debate.parties
        for speaker in party.speakers
        if speaker.video_url
    ]
    if speakers:
        opener = debate.opening_quote.speaker if debate.opening_quote else None
        return next((s for s in speakers if s.speaker == opener), speakers[0])
    cited = next((c for c in debate.citations if c.video_url), None)
    if cited is not None and cited.video_url:
        return CardVideo(
            video_url=_bare(cited.video_url),
            start=_start(cited.url),
            speaker=cited.speaker,
        )
    if debate.video_url:
        return CardVideo(video_url=_bare(debate.video_url), start=MIN_START)
    return None
