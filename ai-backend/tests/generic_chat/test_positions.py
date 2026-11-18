# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Each party's reasons on a law, in tiers; the scope search; the anchor a
turn settles on."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.generic_chat.positions as positions
import src.generic_chat.tools as tools
from src.generic_chat.schemas import Anchor, SearchInput
from src.generic_chat.stream import settled_anchor
from tests.generic_chat.conftest import FakeIO, make_deps

LAW = "338341"


def speech(key: str, party: str, day: str, vorgang: str = LAW) -> dict:
    return {
        "source_type": "parliamentary_speech", "speech_key": key, "chunk_key": key,
        "party_id": party, "publish_date": day, "citation_title": f"Rede {key}",
        "citation_url": f"https://example.org/{key}.pdf", "text": f"Rede {key}",
        "vorgang_ids": [vorgang], "region": "DE", "meta": {},
    }


def drucksache(key: str, text: str, section: str) -> dict:
    return {
        "source_type": "drucksache", "chunk_key": key, "source_parent_key": f"drucksache:BT:{key}",
        "citation_title": f"Drucksache {key}", "publish_date": "2026-11-11", "text": text,
        "doc_section": section, "meta": {"doc_type": "Änderungsantrag", "urheber": []},
    }


@pytest.fixture
def corpus(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    async def view(vorgang_id: str, *, party_id: Any = None, **_: Any) -> Any:
        speeches = [
            speech("s1", "spd", "2026-09-24"), speech("s2", "spd", "2026-11-13"),
            speech("s3", "cdu", "2026-09-24"),
        ]
        return SimpleNamespace(
            speeches=[s for s in speeches if party_id in (None, s["party_id"])], votes=[]
        )

    async def retrieve(query: str, **kw: Any) -> list[dict]:
        calls.append(kw)
        if kw.get("source_type") == "drucksache" and kw.get("doc_section") == ["report"]:
            return [
                drucksache("r1", "Die Fraktion der SPD betonte, der Entwurf sei nötig.", "report"),
                drucksache("r2", "Die Fraktion der AfD lehnte ab.", "report"),
            ]
        if kw.get("source_type") == "drucksache":
            return [drucksache("21/9163", "Änderungsantrag", "overview")] if kw.get("party_id") == "spd" else []
        if kw.get("source_type") == "parliamentary_speech":
            return [speech("s9", kw["party_id"], "2026-01-29", vorgang="1"), speech("s1", "spd", "2026-09-24")]
        return [{"source_type": "party_manifesto", "party_id": kw["party_id"], "citation_title": "Programm",
                 "citation_url": "https://example.org/p.pdf", "publish_date": "2025-02-23", "text": "…",
                 "meta": {"page_start": 3}}]

    monkeypatch.setattr(positions.procedure_service, "aget_procedure_view", view)
    monkeypatch.setattr(positions, "retrieve", retrieve)
    return calls


async def test_a_party_is_heard_from_the_law_first_then_its_record(corpus: list[dict]) -> None:
    docs = await positions.party_positions(make_deps(), [LAW], ["spd"], "Nachrichtendienste")

    tiers = [(d.tier, d.source_type, d.title) for d in docs]
    assert tiers[:4] == [
        ("this_procedure", "parliamentary_speech", "Rede s2"),  # newest reading first
        ("this_procedure", "parliamentary_speech", "Rede s1"),
        ("this_procedure", "drucksache", "Drucksache 21/9163"),  # its own amendment
        ("this_procedure", "drucksache", "Drucksache r1"),  # the report names the SPD
    ]
    # Context leaves out the speeches of the law itself.
    assert [t for t in tiers if t[0] == "context"] == [
        ("context", "parliamentary_speech", "Rede s9"),
        ("context", "party_manifesto", "Programm"),
    ]


async def test_speeches_already_shown_are_not_repeated(corpus: list[dict]) -> None:
    docs = await positions.party_positions(
        make_deps(), [LAW], ["spd"], "Nachrichtendienste", skip={"Rede s2"}
    )
    assert [d.title for d in docs if d.tier == "this_procedure" and d.source_type == "parliamentary_speech"] == ["Rede s1"]


async def test_unknown_parties_and_no_procedure_give_nothing(corpus: list[dict]) -> None:
    assert await positions.party_positions(make_deps(), [LAW], ["fdp"], "x") == []
    assert await positions.party_positions(make_deps(), [], ["spd"], "x") == []


async def test_search_with_a_scope_puts_the_procedure_first(
    fake_io: FakeIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside = speech("in", "spd", "2026-09-24")
    outside = speech("out", "spd", "2026-01-29", vorgang="1")
    fake_io.retrieve_results["parliamentary_speech"] = [(outside, 0.9)]

    async def retrieve(query: str, **kw: Any) -> list:
        if kw.get("vorgang_id") == LAW:
            return [inside]
        return await FakeIO.retrieve(fake_io, query, **kw)

    monkeypatch.setattr(tools, "retrieve", retrieve)

    async def no_procedures(_: list[dict]) -> dict:
        return {}

    monkeypatch.setattr(tools, "aprocedures_for_chunks", no_procedures)
    deps = make_deps()
    deps.add_scope([LAW])
    result = await tools.search(deps, SearchInput(query="Nachrichtendienste", source_types=["parliamentary_speech"]))

    assert [(d.title, d.tier) for d in result.documents] == [
        ("Rede in", "this_procedure"), ("Rede out", "context"),
    ]


async def test_search_without_a_scope_is_unchanged(fake_io: FakeIO) -> None:
    fake_io.retrieve_results["parliamentary_speech"] = [(speech("out", "spd", "2026-01-29"), 0.9)]
    result = await tools.search(make_deps(), SearchInput(query="Mieten", source_types=["parliamentary_speech"]))
    assert [d.tier for d in result.documents] == [None]
    assert all("vorgang_id" not in call for call in fake_io.retrieve_calls)


def test_the_anchor_a_turn_settles_on() -> None:
    deps = make_deps()
    assert settled_anchor(deps) is None
    deps.settle(Anchor(vorgang_id=LAW))
    assert settled_anchor(deps) == Anchor(vorgang_id=LAW)
    # The vote is more specific than its law.
    deps.settle(Anchor(feed_item_id="bundestag_2026-11-13_v6771"))
    assert settled_anchor(deps) == Anchor(feed_item_id="bundestag_2026-11-13_v6771")
    # Two votes: the turn was a recap, nothing to pin.
    deps.settle(Anchor(poll_id=6772))
    assert settled_anchor(deps) is None


async def test_a_tool_never_takes_an_id_no_tool_showed(fake_io: FakeIO) -> None:
    from types import SimpleNamespace

    from src.generic_chat import agent
    from src.generic_chat.schemas import GetProcessInput, GetVoteInput
    from tests.generic_chat.conftest import POLL_ID, vote_payload

    fake_io.votes[POLL_ID] = [vote_payload()]
    deps = make_deps()
    ctx = SimpleNamespace(deps=deps)

    made_up = await agent.get_vote(ctx, GetVoteInput(poll_id=12608))  # type: ignore[arg-type]
    assert made_up.documents == [] and "not returned by any tool" in (made_up.note or "")
    unknown = await agent.get_process(ctx, GetProcessInput(vorgang_id="999"))  # type: ignore[arg-type]
    assert unknown.procedure is None and "not returned by any tool" in (unknown.note or "")

    # Once a tool shows the vote, its id works.
    fake_io.retrieve_results["vote_record"] = [(vote_payload(), 0.9)]
    found = await agent.search(ctx, SearchInput(query="Mietpreisbremse", source_types=["vote_record"]))  # type: ignore[arg-type]
    assert found.documents[0].poll_id == POLL_ID
    vote = await agent.get_vote(ctx, GetVoteInput(poll_id=POLL_ID))  # type: ignore[arg-type]
    assert vote.documents and vote.documents[0].source_type == "vote_record"
