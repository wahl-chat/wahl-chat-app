# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""A feed button's question: each Fraktion's material is fetched in code,
web search is off, and the answer is cached until its data changes."""

from __future__ import annotations

from typing import Any, Optional

import pytest

import src.generic_chat.presets as presets
import src.generic_chat.tools as tools
from src.generic_chat.schemas import Anchor, GenericChatDeps
from tests.generic_chat.conftest import POLL_ID, FakeIO, make_deps
from tests.generic_chat.test_stream import Script, _events, _run, say, turn_io  # noqa: F401 (fixture)

WHY = "Warum haben die Fraktionen so abgestimmt?"


@pytest.fixture()
def cache(monkeypatch: pytest.MonkeyPatch) -> dict[str, presets.CachedTurn]:
    store: dict[str, presets.CachedTurn] = {}

    async def aload(key: str) -> Optional[presets.CachedTurn]:
        return store.get(key)

    async def astore(key: str, turn: presets.CachedTurn) -> None:
        store[key] = turn

    monkeypatch.setattr(presets, "aload", aload)
    monkeypatch.setattr(presets, "astore", astore)
    return store


@pytest.fixture()
def asked(monkeypatch: pytest.MonkeyPatch) -> list[Optional[list[str]]]:
    """The party ids each anchor resolution asked for."""
    calls: list[Optional[list[str]]] = []
    resolve = tools.resolve_anchor

    async def spy(deps: GenericChatDeps, anchor: Anchor, party_ids: Any = None) -> Any:
        calls.append(party_ids)
        return await resolve(deps, anchor, party_ids)

    monkeypatch.setattr(tools, "resolve_anchor", spy)
    return calls


def _answer(parts: list[Any]) -> str:
    return str(_events(parts, "party_complete")[0]["complete_message"])


async def test_the_why_button_brings_every_fraktion_and_no_web(
    turn_io: FakeIO, cache: dict, asked: list, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    script = Script(say("Die SPD stimmte mit Ja [0]."))
    await _run(script, monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why")

    assert asked == [["spd", "cdu"]]  # the Fraktionen, not Volt
    tools_seen = {t.name for t in script.requests[0][1].function_tools}
    assert "web_search" not in tools_seen and "get_vote" in tools_seen


async def test_the_same_button_again_comes_from_the_cache(
    turn_io: FakeIO, cache: dict, asked: list, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    first = await _run(
        Script(say("Die SPD stimmte mit Ja [0].")), monkeypatch,
        user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why",
    )
    assert len(cache) == 1

    replay = Script(say("never asked"))
    again = await _run(replay, monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why")

    assert replay.requests == []
    assert _answer(again) == _answer(first)
    assert _events(again, "sources_ready")[0]["sources"] == _events(first, "sources_ready")[0]["sources"]
    assert _events(again, "quick_replies_title")[0]["quick_replies"] == ["Wer war dagegen?"]


async def test_new_data_on_the_item_misses_the_cache(
    turn_io: FakeIO, cache: dict, asked: list, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    await _run(Script(say("Ja [0].")), monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="ask")
    turn_io.votes[POLL_ID][0]["text"] = "Neue Fassung des Abstimmungstexts"
    fresh = Script(say("Neu [0]."))
    await _run(fresh, monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="ask")

    assert len(fresh.requests) == 1 and len(cache) == 2


async def test_typed_questions_and_follow_ups_are_not_cached(
    turn_io: FakeIO, cache: dict, asked: list, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    typed = Script(say("Ja [0]."))
    await _run(typed, monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID})
    follow_up = Script(say("Die CDU [0]."))
    await _run(
        follow_up, monkeypatch, user_message="Und die CDU?", anchor={"poll_id": POLL_ID},
        preset="why", chat_history=[
            {"role": "user", "content": WHY}, {"role": "assistant", "content": "Ja."},
        ],
    )

    assert cache == {} and asked == [None, None]
    assert "web_search" in {t.name for t in follow_up.requests[0][1].function_tools}


async def test_get_vote_without_an_id_takes_the_chat_vote(fake_io: FakeIO) -> None:
    from types import SimpleNamespace

    from src.generic_chat import agent
    from src.generic_chat.schemas import GetVoteInput
    from tests.generic_chat.conftest import vote_payload

    fake_io.votes[POLL_ID] = [vote_payload()]
    deps = make_deps()
    ctx = SimpleNamespace(deps=deps)
    lost = await agent.get_vote(ctx, GetVoteInput())  # type: ignore[arg-type]
    assert lost.documents == [] and "not about one vote" in (lost.note or "")

    deps.anchor = await tools.resolve_anchor(deps, Anchor(poll_id=POLL_ID))
    found = await agent.get_vote(ctx, GetVoteInput(party_ids=["spd"]))  # type: ignore[arg-type]
    assert found.documents[0].poll_id == POLL_ID


async def test_a_citation_the_check_re_points_reaches_the_answer_and_the_cache(
    turn_io: FakeIO, cache: dict, asked: list, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from src.generic_chat import citation_check, stream
    from tests.generic_chat.conftest import manifesto_payload
    from tests.generic_chat.test_stream import call

    monkeypatch.setenv(citation_check.ENV, "on")
    turn_io.retrieve_results = {
        "party_manifesto": [
            (manifesto_payload("volt"), 0.7),
            ({**manifesto_payload("volt"), "citation_title": "volt Kurzprogramm"}, 0.6),
        ]
    }

    async def check(answer: str, sources: Any, model: Any = None) -> citation_check.CheckResult:
        # The second Volt programme states it, not the first.
        return citation_check.CheckResult(
            verdicts=[citation_check.Verdict(s, {2}) for s in citation_check.cited_sentences(answer)]
        )

    monkeypatch.setattr(stream.citation_check, "check", check)
    script = Script(
        call(("search", {"query": "Mieten", "source_types": ["party_manifesto"]})),
        say("Volt will bezahlbare Mieten [1]."),
    )
    parts = await _run(script, monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="ask")

    assert _answer(parts) == "Volt will bezahlbare Mieten [2]."
    assert next(iter(cache.values())).answer == "Volt will bezahlbare Mieten [2]."


async def test_a_failing_check_keeps_the_answer(
    turn_io: FakeIO, cache: dict, asked: list, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from src.generic_chat import citation_check, stream

    monkeypatch.setenv(citation_check.ENV, "on")

    async def broken(*_args: Any, **_kwargs: Any) -> citation_check.CheckResult:
        raise RuntimeError("model down")

    monkeypatch.setattr(stream.citation_check, "check", broken)
    parts = await _run(Script(say("Die SPD stimmte mit Ja [0].")), monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID})
    assert _answer(parts) == "Die SPD stimmte mit Ja [0]."
