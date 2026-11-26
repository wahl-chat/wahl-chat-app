# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""A failing lookup never ends a turn, and an answer built on one is not cached."""

from __future__ import annotations

from typing import Any

import pytest

import src.generic_chat.presets as presets
import src.generic_chat.tools as tools
from src.generic_chat import citation_check, stream
from src.generic_chat.schemas import NumberedDocument, ProcessResult, ProcessStep
from tests.generic_chat.conftest import POLL_ID, FakeIO, make_deps
from tests.generic_chat.test_stream import Script, _events, _run, call, say, turn_io  # noqa: F401 (fixture)

WHY = "Warum haben die Fraktionen so abgestimmt?"


@pytest.fixture()
def cache(monkeypatch: pytest.MonkeyPatch) -> dict[str, presets.CachedTurn]:
    store: dict[str, presets.CachedTurn] = {}

    async def aload(key: str) -> Any:
        return store.get(key)

    async def astore(key: str, turn: presets.CachedTurn) -> None:
        store[key] = turn

    monkeypatch.setattr(presets, "aload", aload)
    monkeypatch.setattr(presets, "astore", astore)
    return store


def _answer(parts: list[Any]) -> str:
    return str(_events(parts, "party_complete")[0]["complete_message"])


async def test_a_failing_anchor_leaves_the_turn_standing(
    turn_io: FakeIO, cache: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    async def down(*_a: Any, **_k: Any) -> Any:
        raise ConnectionError("qdrant down")

    monkeypatch.setattr(tools, "resolve_anchor", down)
    parts = await _run(Script(say("Dazu liegen keine Quellen vor.")), monkeypatch,
                       user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why")
    assert _answer(parts) == "Dazu liegen keine Quellen vor."
    assert _events(parts, "error") == [] and cache == {}


async def test_a_failing_tool_becomes_a_note(turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    async def down(*_a: Any, **_k: Any) -> Any:
        raise TimeoutError("firestore")

    monkeypatch.setattr(tools, "search", down)
    script = Script(call(("search", {"query": "Mieten"})), say("Ohne Quellen."))
    parts = await _run(script, monkeypatch)
    assert _answer(parts) == "Ohne Quellen." and _events(parts, "error") == []
    returned = str(script.requests[1][0][-1])
    assert "lookup failed" in returned


async def test_a_slow_tool_twice_still_gets_an_answer(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    import asyncio

    from src.generic_chat import agent

    async def slow(*_a: Any, **_k: Any) -> Any:
        await asyncio.sleep(1)

    monkeypatch.setattr(agent, "_CALL_TIMEOUT_S", 0.05)
    monkeypatch.setattr(tools, "search", slow)
    script = Script(
        call(("search", {"query": "Mieten"})),
        call(("search", {"query": "Mieten Berlin"})),
        say("Ohne Quellen."),
    )
    parts = await _run(script, monkeypatch)
    assert _answer(parts) == "Ohne Quellen." and _events(parts, "error") == []
    assert "lookup failed" in str(script.requests[2][0][-1])


async def test_a_preset_answer_on_a_failed_check_is_not_cached(
    turn_io: FakeIO, cache: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setenv(citation_check.ENV, "on")

    async def broken(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("model down")

    monkeypatch.setattr(stream.citation_check, "check", broken)
    await _run(Script(say("Ja [0].")), monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why")
    assert cache == {}


async def test_steps_are_checked_and_unshown_sources_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(citation_check.ENV, "on")
    deps = make_deps()
    step = deps.sources.register({"source": "1. Beratung", "url": "https://x/1.pdf", "source_type": "procedure_step"})
    hidden = deps.sources.register({"source": "Drucksache", "url": "https://x/2.pdf", "source_type": "drucksache"})
    documents = stream._documents_of(ProcessResult(steps=[ProcessStep(id=step, date="2026-09-08", chamber="BT", name="1. Beratung")]))
    seen: list[Any] = []

    async def check(answer: str, sources: Any, model: Any = None) -> citation_check.CheckResult:
        seen.extend(sources)
        return citation_check.CheckResult(
            verdicts=[citation_check.Verdict(s, set()) for s in citation_check.cited_sentences(answer)]
        )

    monkeypatch.setattr(stream.citation_check, "check", check)
    answer = await stream._checked(f"Erste Beratung am 8. September [{step}]. Mehr [{hidden}].", deps, documents)
    assert [s.id for s in seen] == [step] and "2026-09-08" in seen[0].text
    assert answer == f"Erste Beratung am 8. September. Mehr [{hidden}]."


def test_voices_tell_parties_records_and_press_apart() -> None:
    deps = make_deps()
    speech = deps.sources.register({"source": "Günter Krings, 2026-11-13 (Video)", "url": "a", "party_id": "csu", "source_type": "parliamentary_speech"})
    vote = deps.sources.register({"source": "Abstimmung", "url": "b", "source_type": "vote_record"})
    press = deps.sources.register({"source": "tagesschau", "url": "c", "source_type": "web"})
    site = deps.sources.register({"source": "SPD-Fraktion", "url": "d", "source_type": "web", "party_id": "spd"})
    assert [stream._voice(deps, n) for n in (speech, vote, press, site)] == ["cdu", "record", "press", "spd"]
    assert stream._speaker(deps, speech) == "Günter Krings" and stream._speaker(deps, vote) is None


def test_a_fraktion_page_is_that_party_speaking() -> None:
    from src.generic_chat import web_context
    from src.generic_chat.schemas import WebResult

    deps = make_deps()
    docs = web_context.register_results(deps, [
        WebResult(title="Fraktion <b>", url="https://www.spdfraktion.de/x", snippet="…", date="2026-11-13", domain="spdfraktion.de", preferred=True),
        WebResult(title="Tagesschau", url="https://www.tagesschau.de/x", snippet="…", date="2026-11-13", domain="tagesschau.de", preferred=True),
    ], "press")
    assert [(d.tier, d.preferred_outlet) for d in docs] == [("party_site", None), ("press", True)]
    assert deps.sources.entries[docs[0].id]["party_id"] == "spd"
    assert isinstance(docs[0], NumberedDocument)


async def test_a_cached_answer_carries_its_expiry(
    turn_io: FakeIO, cache: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    await _run(Script(say("Ja [0].")), monkeypatch, user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why")
    turn = next(iter(cache.values()))
    assert turn.expire_at is not None and turn.expire_at - turn.created_at == presets.MAX_AGE


async def test_a_bare_number_as_name_is_checked_like_an_id() -> None:
    from types import SimpleNamespace

    from src.generic_chat import agent
    from src.generic_chat.schemas import GetProcessInput

    ctx = SimpleNamespace(deps=make_deps())
    result = await agent.get_process(ctx, GetProcessInput(name="12345"))  # type: ignore[arg-type]
    assert result.procedure is None and "not returned by any tool" in (result.note or "")


async def test_the_cache_is_written_before_the_stream_ends(
    turn_io: FakeIO, cache: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setattr(stream, "resolve_model", lambda: Script(say("Ja [0].")).model)
    from tests.generic_chat.test_stream import _body, general_context

    async for _ in stream.stream_generic_chat(
        _body(user_message=WHY, anchor={"poll_id": POLL_ID}, preset="why"), None, general_context()
    ):
        pass
    assert len(cache) == 1


async def test_web_search_marks_a_party_page_as_that_party(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.generic_chat import web_search as web
    from src.generic_chat.schemas import WebResult, WebSearchInput

    async def search_web(*_a: Any, **_k: Any) -> Any:
        return [
            WebResult(title="AfD", url="https://afdbundestag.de/x", snippet="…", date="2026-11-13", domain="afdbundestag.de", preferred=False),
            WebResult(title="Spiegel", url="https://www.spiegel.de/x", snippet="…", date="2026-11-13", domain="spiegel.de", preferred=True),
            WebResult(title="Blog", url="https://blog.example/x", snippet="…", date="2026-11-13", domain="blog.example", preferred=False),
        ], None

    monkeypatch.setattr(web, "search_web", search_web)
    deps = make_deps()
    result = await tools.web_search(deps, WebSearchInput(query="Rente", scope="news"))
    assert [(d.tier, d.preferred_outlet) for d in result.documents] == [
        ("party_site", None), (None, True), (None, False),
    ]
    assert deps.sources.entries[result.documents[0].id]["party_id"] == "afd"
