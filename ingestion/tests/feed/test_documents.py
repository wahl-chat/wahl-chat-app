# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from typing import Any

from ingestion.feed.documents import (
    drucksachen_in_links,
    drucksachen_in_text,
    poll_documents,
)

# Shaped like abgeordnetenwatch's poll intro for the GKV reform (poll 6601).
INTRO = (
    '<p>Der <a href="https://dserver.bundestag.de/btd/21/061/2106130.pdf">'
    "Gesetzentwurf</a> und die "
    '<a href="https://dserver.bundestag.de/btd/21/070/2107016.pdf">'
    "Beschlussempfehlung</a>, siehe auch "
    '<a href="https://www.bundestag.de/dokumente">Bundestag</a>.</p>'
)


def test_drucksachen_as_the_protocol_prints_them() -> None:
    text = "Drucksachen 21/6130, 21/7015 und 21/6130 – Bericht 21/7016"
    assert drucksachen_in_text(text) == ["21/6130", "21/7015", "21/7016"]


def test_drucksachen_from_dserver_links_only() -> None:
    assert drucksachen_in_links(INTRO) == ["21/6130", "21/7016"]


class _Client:
    def __init__(self, polls: dict[int, Any]) -> None:
        self.polls = polls

    def get(self, path: str) -> dict:
        poll = self.polls[int(path.split("/")[1])]
        if isinstance(poll, Exception):
            raise poll
        return {"data": poll}


def test_a_poll_lookup_answers_or_says_it_could_not() -> None:
    lookup = poll_documents(
        _Client({1: {"field_intro": INTRO}, 2: {}, 3: ConnectionError("down")})
    )
    assert lookup(1) == ["21/6130", "21/7016"]
    # No linked Drucksache is an answer; a failed lookup is not.
    assert lookup(2) == []
    assert lookup(3) is None
