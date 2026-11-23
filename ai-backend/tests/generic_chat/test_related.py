# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Which feed items count as matching a question."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.generic_chat import related


def _hits(*leads: tuple[str, float, str], background: float = 0.5) -> list[tuple[str, float, str]]:
    top = [(item_id, background + lead, day) for item_id, lead, day in leads]
    rest = [(f"bg{i}", background, "2026-01-01") for i in range(related.BASELINE_RANK - len(top))]
    return top + rest


def test_items_count_by_their_lead_over_the_background() -> None:
    hits = _hits(("a", 0.13, "2026-11-11"), ("b", 0.09, "2026-11-11"), ("c", 0.07, "2026-10-08"))
    # c leads by less than 0.6 of a's lead.
    assert related.select(hits) == ["a", "b"]


def test_unrelated_questions_get_nothing() -> None:
    # A high raw score alone is no match: everything scores high.
    hits = _hits(("a", 0.06, "2026-11-11"), ("b", 0.04, "2026-11-11"), background=0.7)
    assert related.select(hits) == []


def test_one_clear_match_drops_the_tail() -> None:
    hits = _hits(("mercosur", 0.17, "2026-10-07"), ("x", 0.07, "2026-11-11"))
    assert related.select(hits) == ["mercosur"]


def test_close_leads_put_the_newer_item_first() -> None:
    hits = _hits(("old", 0.105, "2026-09-01"), ("new", 0.101, "2026-11-01"), ("far", 0.08, "2026-11-20"))
    assert related.select(hits) == ["new", "old", "far"]


def test_at_most_five() -> None:
    hits = _hits(*[(str(i), 0.2 - i * 0.005, "2026-11-01") for i in range(8)])
    assert len(related.select(hits)) == related.MAX_ITEMS


def test_too_small_a_collection_has_no_background() -> None:
    assert related.select([("a", 0.9, "2026-11-01")]) == []


class _Client:
    def __init__(self, points: list[Any]) -> None:
        self.points = points
        self.calls: list[dict] = []

    async def retrieve(self, **_kwargs: Any) -> list:
        return []

    async def query_points(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(points=self.points)


async def test_find_searches_published_items_of_the_parliament(monkeypatch: Any) -> None:
    async def _embed(query: str) -> list[float]:
        return [0.1]

    monkeypatch.setattr(related, "embed_query", _embed)
    points = [
        SimpleNamespace(score=0.5 + lead, payload={"item_id": item_id, "date": day})
        for item_id, lead, day in [("a", 0.2, "2026-11-01"), ("b", 0.0, "")]
    ] + [SimpleNamespace(score=0.5, payload={"item_id": f"bg{i}"}) for i in range(60)]
    client = _Client(points)

    assert await related.find("Mieten", "bundestag", client=client) == ["a"]

    call = client.calls[0]
    assert call["collection_name"] == related.FEED_COLLECTION_NAME
    assert call["limit"] == related.BASELINE_RANK
    conditions = {c.key: c.match.value for c in call["query_filter"].must}
    assert conditions == {"status": "published", "parliament": "bundestag"}


def test_only_parliaments_with_a_feed_and_real_questions_search(monkeypatch: Any) -> None:
    monkeypatch.setenv(related.ENV, "on")
    question = "Wie stehen die Parteien zum Bürgergeld?"
    assert related.wanted("bundestag", question, has_history=False)
    assert not related.wanted("landtag_st", question, has_history=False)
    assert not related.wanted(None, question, has_history=False)
    assert related.wanted("bundestag", "Bürgergeld", has_history=False)
    assert not related.wanted("bundestag", "Und die SPD?", has_history=True)
    monkeypatch.setenv(related.ENV, "off")
    assert not related.wanted("bundestag", question, has_history=False)


async def test_a_missing_or_small_index_is_left_alone_for_a_while(monkeypatch: Any) -> None:
    monkeypatch.setenv(related.ENV, "on")
    embedded: list[str] = []

    async def _embed(query: str) -> list[float]:
        embedded.append(query)
        return [0.1]

    class _Missing(_Client):
        async def query_points(self, **kwargs: Any) -> Any:
            raise RuntimeError("404 collection not found")

    monkeypatch.setattr(related, "embed_query", _embed)
    with pytest.raises(RuntimeError):
        await related.find("Mieten", "bundestag", client=_Missing([]))
    assert not related.wanted("bundestag", "Mieten", has_history=False)

    monkeypatch.setattr(related, "_unavailable_until", {})
    assert await related.find("Mieten", "bundestag", client=_Client([])) == []
    assert not related.wanted("bundestag", "Mieten", has_history=False)
    assert len(embedded) == 2


