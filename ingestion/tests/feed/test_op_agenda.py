# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from typing import Any

from ingestion.feed.op_agenda import agenda_pages, op_agenda_lookup, session_id


def _item(item_id: str, official: str) -> dict[str, Any]:
    return {
        "type": "agendaItem",
        "id": item_id,
        "attributes": {"officialTitle": official, "title": "", "order": None},
    }


# Trimmed from openparliament.tv's session API for sitting 21/90.
SESSION = {
    "meta": {},
    "data": {
        "type": "session",
        "id": "DE-0210090",
        "relationships": {
            "agendaItems": {
                "data": [
                    _item("15495", "Sitzungseröffnung"),
                    _item("15496", "TOP "),
                    _item("15497", "Tagesordnungspunkt 22"),
                    _item("15498", "Zusatzpunkt 18"),
                    _item("15499", "Tagesordnungspunkt 22a"),
                    _item("15506", "Sitzungsende"),
                ]
            }
        },
    },
}


def test_session_ids_are_padded_as_the_site_writes_them() -> None:
    assert session_id((21, 90)) == "DE-0210090"
    assert session_id((20, 101)) == "DE-0200101"


def test_numbered_agenda_items_by_their_debate_slug() -> None:
    assert agenda_pages(SESSION) == {
        "top22": "https://de.openparliament.tv/agendaItem/DE-15497",
        "zp18": "https://de.openparliament.tv/agendaItem/DE-15498",
    }


def test_a_response_without_agenda_items_lists_none() -> None:
    assert agenda_pages({"data": {}}) == {}
    assert agenda_pages({}) == {}


def test_each_sitting_is_asked_once_and_a_failure_is_no_answer() -> None:
    asked: list[str] = []

    def get_json(url: str) -> dict[str, Any]:
        asked.append(url)
        if "DE-0210091" in url:
            raise ConnectionError("down")
        return SESSION

    lookup = op_agenda_lookup(get_json)
    assert lookup((21, 90)) == agenda_pages(SESSION)
    assert lookup((21, 90)) == agenda_pages(SESSION)
    assert lookup((21, 91)) is None
    assert asked == [
        "https://de.openparliament.tv/api/v1/session/DE-0210090",
        "https://de.openparliament.tv/api/v1/session/DE-0210091",
    ]
