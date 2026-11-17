# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""One generic-chat turn end to end, with a scripted FunctionModel in place
of the LLM (AC-3, AC-4, AC-5, AC-6, AC-12, AC-13)."""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator, Callable

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import (
    AgentInfo,
    DeltaToolCall,
    DeltaToolCalls,
    FunctionModel,
)

import src.generic_chat.stream as stream
from src.generic_chat.schemas import ProcessChoice, ProcessResult
import src.services.chat.service as service
from src.models.structured_outputs import GroupChatTitleQuickReplyGenerator
from src.routes.chat import ChatRequestDto
from tests.generic_chat.conftest import (
    DEBATE_ID,
    POLL_ID,
    SPEECH_IDS,
    FakeIO,
    feed_item,
    general_context,
    manifesto_payload,
    parties,
    speech_chunk,
    vote_payload,
)

Step = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


class Script:
    """A FunctionModel that plays ``steps`` in order and records each request."""

    def __init__(self, *steps: Step) -> None:
        self.steps = list(steps)
        self.requests: list[tuple[list[ModelMessage], AgentInfo]] = []
        self.model = FunctionModel(self._respond, stream_function=self._stream)

    def _respond(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.requests.append((list(messages), info))
        step = self.steps[min(len(self.requests), len(self.steps)) - 1]
        return step(messages, info)

    async def _stream(
        self, messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls]:
        response = self._respond(messages, info)
        for index, part in enumerate(response.parts):
            if isinstance(part, TextPart):
                half = len(part.content) // 2
                yield part.content[:half]
                yield part.content[half:]
            elif isinstance(part, ToolCallPart):
                yield {
                    index: DeltaToolCall(
                        name=part.tool_name,
                        json_args=part.args_as_json_str(),
                        tool_call_id=part.tool_call_id,
                    )
                }


def call(*calls: tuple[str, dict]) -> Step:
    return lambda _m, _i: ModelResponse(
        parts=[
            ToolCallPart(name, args, tool_call_id=f"call-{name}-{n}")
            for n, (name, args) in enumerate(calls)
        ]
    )


def say(text: str) -> Step:
    return lambda _m, _i: ModelResponse(parts=[TextPart(text)])


@pytest.fixture()
def turn_io(fake_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> FakeIO:
    async def _parties(context_id: str) -> list:
        return parties()

    async def _quick_replies(**_kwargs: Any) -> GroupChatTitleQuickReplyGenerator:
        return GroupChatTitleQuickReplyGenerator(
            chat_title="Mietpreisbremse", quick_replies=["Wer war dagegen?"]
        )

    monkeypatch.setattr(stream, "aget_parties_for_context", _parties)
    monkeypatch.setattr(stream, "generate_chat_title_and_chick_replies", _quick_replies)
    fake_io.votes[POLL_ID] = [vote_payload()]
    fake_io.retrieve_results = {"party_manifesto": [(manifesto_payload("volt"), 0.7)]}
    return fake_io


def _body(**extra: Any) -> ChatRequestDto:
    return ChatRequestDto.model_validate(
        {
            "session_id": "s-1",
            "context_id": "bundestag-aktuell",
            "user_message": "Wie hat die SPD zur Mietpreisbremse abgestimmt?",
            **extra,
        }
    )


async def _run(script: Script, monkeypatch: pytest.MonkeyPatch, **extra: Any) -> list[Any]:
    monkeypatch.setattr(stream, "resolve_model", lambda: script.model)
    return [
        part if part == "[DONE]" else json.loads(part)
        async for part in stream.stream_generic_chat(_body(**extra), None, general_context())
    ]


def _kinds(parts: list[Any]) -> list[str]:
    kinds = []
    for part in parts:
        if part == "[DONE]":
            kinds.append("[DONE]")
        elif part["type"] == "data-chat_event":
            kinds.append(part["data"]["type"])
        else:
            kinds.append(part["type"])
    return kinds


def _collapse(kinds: list[str]) -> list[str]:
    out: list[str] = []
    for kind in kinds:
        if kind == "party_chunk":
            continue
        if not out or out[-1] != kind or kind not in {"text-delta", "tool_status"}:
            out.append(kind)
    return out


def _events(parts: list[Any], kind: str) -> list[dict]:
    return [
        p["data"] for p in parts
        if p != "[DONE]" and p["type"] == "data-chat_event" and p["data"]["type"] == kind
    ]


async def test_event_order_and_sources(turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(
        call(("get_vote", {"poll_id": POLL_ID}), ("search", {"query": "Mietpreisbremse", "source_types": ["party_manifesto"]})),
        say("Die SPD stimmte mit Ja [0]. Volt (nicht im Bundestag) will bezahlbare Mieten [1]."),
    )

    parts = await _run(script, monkeypatch)
    kinds = _kinds(parts)

    assert _collapse(kinds) == [
        "start", "start-step", "responding_parties", "tool_status", "sources_ready",
        "text-start", "text-delta", "text-end", "party_complete", "quick_replies_title",
        "finish-step", "finish", "[DONE]",
    ]
    assert _events(parts, "responding_parties")[0]["party_ids"] == ["wahl-chat"]

    statuses = _events(parts, "tool_status")
    assert {(s["tool"], s["state"]) for s in statuses} == {
        ("get_vote", "running"), ("search", "running"), ("get_vote", "done"), ("search", "done"),
    }
    assert {s["label"] for s in statuses if s["tool"] == "get_vote"} == {
        "Suche Abstimmung …", "Abstimmung nachgeschlagen",
    }
    assert all(s["session_id"] == "s-1" and s["call_id"] for s in statuses)

    sources = _events(parts, "sources_ready")[0]
    assert sources["party_id"] == "wahl-chat"
    assert [s["source_type"] for s in sources["sources"]] == ["vote_record", "party_manifesto"]

    complete = _events(parts, "party_complete")[0]
    assert complete["party_id"] == "wahl-chat" and complete["status"]["indicator"] == "success"
    text = "".join(p["delta"] for p in parts if p != "[DONE]" and p["type"] == "text-delta")
    assert complete["complete_message"] == text
    assert _events(parts, "quick_replies_title")[0]["quick_replies"] == ["Wer war dagegen?"]


async def test_citation_numbers_index_sources_ready(turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> None:
    """The model cites the id a tool returned; that id is the source's
    0-based position in sources_ready (how the web resolves [n])."""
    seen_ids: dict[str, int] = {}

    def answer(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        for message in messages:
            for part in getattr(message, "parts", []):
                if part.part_kind == "tool-return":
                    for doc in part.content.documents:
                        seen_ids[doc.source_type] = doc.id
        return ModelResponse(
            parts=[TextPart(f"Stimme [{seen_ids['vote_record']}], Programm [{seen_ids['party_manifesto']}].")]
        )

    script = Script(
        call(("search", {"query": "Mietpreisbremse", "source_types": ["party_manifesto"]})),
        call(("get_vote", {"poll_id": POLL_ID})),
        answer,
    )
    parts = await _run(script, monkeypatch)

    sources = _events(parts, "sources_ready")[-1]["sources"]
    answer_text = _events(parts, "party_complete")[0]["complete_message"]
    cited = [int(n) for n in re.findall(r"\[(\d+)\]", answer_text)]
    assert [sources[n]["source_type"] for n in cited] == ["vote_record", "party_manifesto"]
    assert cited == [1, 0]


async def test_request_limit_forces_an_answer(turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> None:
    def greedy(_m: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.function_tools:
            return ModelResponse(parts=[ToolCallPart("search", {"query": "Mieten Berlin"})])
        return ModelResponse(parts=[TextPart("Antwort aus den bisherigen Quellen [0].")])

    script = Script(greedy)
    parts = await _run(script, monkeypatch)

    assert len(script.requests) == 4
    assert [bool(info.function_tools) for _m, info in script.requests] == [True, True, True, False]
    complete = _events(parts, "party_complete")[0]
    assert complete["status"]["indicator"] == "success"
    assert complete["complete_message"].startswith("Antwort")


async def test_language_rule_follows_tool_results_without_piling_up(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = Script(
        call(("get_vote", {"poll_id": POLL_ID})),
        call(("search", {"query": "Mietpreisbremse"})),
        say("The SPD voted yes [0]."),
    )
    await _run(script, monkeypatch, language="en")

    for messages, info in script.requests[1:]:
        last = messages[-1]
        assert isinstance(last, ModelRequest)
        assert isinstance(last.parts[-1], UserPromptPart)
        assert "answer in English" in str(last.parts[-1].content)
        reminders = [
            p for m in messages if isinstance(m, ModelRequest) for p in m.parts
            if isinstance(p, UserPromptPart) and "Answer in the language" in str(p.content)
        ]
        assert len(reminders) == 1
    assert "answer in English" in (script.requests[0][1].instructions or "")


async def test_anchor_sources_come_first(turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> None:
    turn_io.feed[DEBATE_ID] = feed_item(DEBATE_ID, "debate", speech_ids=SPEECH_IDS[:1])
    turn_io.speeches = [speech_chunk(SPEECH_IDS[0], 0, "Rede zur Mietpreisbremse.")]
    script = Script(
        call(("search", {"query": "Mietpreisbremse", "source_types": ["party_manifesto"]})),
        say("In der Debatte begründete die SPD … [0]."),
    )

    parts = await _run(script, monkeypatch, anchor={"feed_item_id": DEBATE_ID})

    statuses = _events(parts, "tool_status")
    assert (statuses[0]["call_id"], statuses[0]["tool"], statuses[0]["state"]) == ("anchor", "get_debate", "running")
    assert _kinds(parts).index("tool_status") < _kinds(parts).index("sources_ready")
    sources = _events(parts, "sources_ready")[0]["sources"]
    assert [s["source_type"] for s in sources] == ["parliamentary_speech", "party_manifesto"]
    assert "## Bezug" in (script.requests[0][1].instructions or "")
    assert "Schlagzeile" in (script.requests[0][1].instructions or "")


async def test_focus_from_the_request_scopes_search_and_prompt(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn_io.feed[DEBATE_ID] = feed_item(DEBATE_ID, "debate", speech_ids=SPEECH_IDS[:1])
    turn_io.speeches = [speech_chunk(SPEECH_IDS[0], 0, "Rede zur Mietpreisbremse.")]
    script = Script(
        call(("search", {"query": "Mietpreisbremse", "source_types": ["party_manifesto"]})),
        say("Volt will bezahlbare Mieten [1]."),
    )

    await _run(
        script,
        monkeypatch,
        party_ids=["volt", "nope"],
        anchor={"feed_item_id": DEBATE_ID},
    )

    instructions = script.requests[0][1].instructions or ""
    assert "## Fokus\nThe user pinned these parties for this chat:\n- Volt, id volt\n" in instructions
    assert "nope" not in instructions
    assert "## Bezug" in instructions
    assert {c["party_id"] for c in turn_io.retrieve_calls} == {"volt"}


async def test_unknown_anchor_answers_normally(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")
    script = Script(say("Dazu habe ich keine Quellen."))

    parts = await _run(script, monkeypatch, anchor={"poll_id": 424242})

    assert "anchor miss" in caplog.text
    assert _events(parts, "sources_ready")[0]["sources"] == []
    assert _events(parts, "party_complete")[0]["status"]["indicator"] == "success"
    assert "## Bezug" not in (script.requests[0][1].instructions or "")


async def test_model_failure_ends_with_the_error_contract(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_m: list[ModelMessage], _i: AgentInfo) -> ModelResponse:
        raise RuntimeError("model down")

    parts = await _run(Script(broken), monkeypatch)

    assert _kinds(parts)[-5:] == ["error", "party_complete", "finish-step", "finish", "[DONE]"]
    assert _events(parts, "party_complete")[0]["status"]["indicator"] == "error"


async def test_history_drops_old_citations(turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch) -> None:
    script = Script(say("Ja."))
    await _run(
        script,
        monkeypatch,
        chat_history=[
            {"role": "user", "content": "Frage eins"},
            {"role": "assistant", "content": "Antwort [0][2, 3].", "party_id": "wahl-chat"},
            {"role": "user", "content": "Wie hat die SPD zur Mietpreisbremse abgestimmt?"},
        ],
    )
    messages = script.requests[0][0]
    texts = [p.content for m in messages for p in m.parts if isinstance(p, (TextPart, UserPromptPart))]
    assert texts == ["Frage eins", "Antwort.", "Wie hat die SPD zur Mietpreisbremse abgestimmt?"]


# --- routing in the chat service (AC-3) ------------------------------------


async def test_general_context_bypasses_the_party_pipeline(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _context(_context_id: str):
        return general_context()

    async def _forbidden(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("election pipeline must not run for a general context")

    monkeypatch.setattr(service, "aget_context_by_id", _context)
    monkeypatch.setattr(service, "aget_parties_for_context", _forbidden)
    monkeypatch.setattr(service, "get_question_targets_and_type", _forbidden)
    monkeypatch.setattr(service, "detect_source_filter", _forbidden)
    monkeypatch.setattr(service, "fetch_party_response_stream", _forbidden)
    monkeypatch.setattr(stream, "resolve_model", lambda: Script(say("Hallo [0].")).model)

    parts = [
        part if part == "[DONE]" else json.loads(part)
        async for part in service.generate_chat_stream(_body(), None)
    ]
    assert _events(parts, "responding_parties")[0]["party_ids"] == ["wahl-chat"]
    assert _events(parts, "party_complete")[0]["status"]["indicator"] == "success"
    assert parts[-1] == "[DONE]"


async def test_open_procedure_choices_become_quick_replies(
    turn_io: FakeIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    choices = [
        ProcessChoice(vorgang_id="338366", label="Haushaltsbegleitgesetz 2027 (WP 21)"),
        ProcessChoice(vorgang_id="338317", label="Haushaltsgesetz 2027 (WP 21)"),
    ]

    async def _get_process(deps: Any, args: Any, **_: Any) -> ProcessResult:
        return ProcessResult(choices=choices, note="Ask the user.")

    monkeypatch.setattr(stream.agent_module.process, "get_process", _get_process)
    script = Script(
        call(("get_process", {"name": "Haushalt 2027"})),
        say("Welches Verfahren meinst du?"),
    )

    parts = await _run(script, monkeypatch, user_message="Wie ist der Stand beim Haushalt 2027?")

    assert _events(parts, "quick_replies_title")[0]["quick_replies"] == [c.label for c in choices]
