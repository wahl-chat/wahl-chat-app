# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

from ingestion import llm_clients
from ingestion.feed import builder as builder_module
from ingestion.feed import publication_llms


class Answer(BaseModel):
    text: str


def test_feed_texts_go_to_the_publication_roster_without_chat_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake(
        roster: list, messages: list, schema: type, **kwargs: Any
    ) -> tuple[Any, str]:
        seen.update(roster=roster, kwargs=kwargs)
        return Answer(text="ok"), "entry"

    monkeypatch.setattr(publication_llms, "structured_output_with_failover", fake)
    result, model = asyncio.run(builder_module._default_structured_output([], Answer))
    assert (result.text, model) == ("ok", "entry")
    assert seen["roster"] is publication_llms.publication_llms()
    assert seen["kwargs"] == {}


def test_the_publication_roster_reasons_at_length() -> None:
    roster = publication_llms.publication_llms()
    assert roster
    for entry in roster:
        assert "lite" not in entry.name
        effort = getattr(entry.model, "thinking_level", None) or getattr(
            entry.model, "reasoning_effort", None
        )
        assert effort == publication_llms.PUBLICATION_THINKING == "high"


class _Failing:
    def with_structured_output(self, schema: type) -> "_Failing":
        return self

    async def ainvoke(self, messages: list) -> Any:
        raise RuntimeError("quota")


def test_an_exhausted_batch_roster_does_not_flag_the_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roster = [llm_clients.RosterLLM(name="x", model=_Failing(), priority=1)]  # type: ignore[arg-type]
    monkeypatch.setattr(publication_llms, "publication_llms", lambda: roster)
    flagged: list[bool] = []

    with pytest.raises(Exception, match="All LLMs failed"):
        asyncio.run(
            publication_llms.structured_output_from_publication_llms([], Answer)
        )
    assert flagged == []
    with pytest.raises(Exception, match="All LLMs failed"):
        asyncio.run(
            llm_clients.structured_output_with_failover(
                roster, [], Answer, on_primaries_exhausted=lambda: flagged.append(True)
            )
        )
    assert flagged == [True]


def _roster_names(monkeypatch: pytest.MonkeyPatch, *, vertex: bool) -> set[str]:
    real = publication_llms.gemini

    def gemini(model: str, *, vertex: bool = False, **kwargs: Any) -> Any:
        # Only the Vertex client is faked (it needs real credentials); an AI
        # Studio client is built for real, so building one without a key fails.
        return object() if vertex else real(model, vertex=vertex, **kwargs)

    monkeypatch.setattr(publication_llms, "vertex_enabled", lambda: vertex)
    monkeypatch.setattr(publication_llms, "vertex_project", lambda: "project")
    monkeypatch.setattr(publication_llms, "gemini", gemini)
    return {entry.name for entry in publication_llms._build_publication_llms()}


def test_an_ai_studio_client_cannot_be_built_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert not llm_clients.ai_studio_enabled()
    with pytest.raises(Exception, match="API key"):
        llm_clients.gemini("gemini-3.6-flash")


def test_the_roster_runs_on_vertex_without_an_ai_studio_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert _roster_names(monkeypatch, vertex=True) == {
        "vertex-gemini-3.6-flash-high",
        "vertex-gemini-3.7-flash-high",
        "openai-gpt-5.6-terra-high",
    }


def test_ai_studio_joins_the_roster_behind_vertex_when_a_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "key")
    assert _roster_names(monkeypatch, vertex=True) == {
        "vertex-gemini-3.6-flash-high",
        "vertex-gemini-3.7-flash-high",
        "openai-gpt-5.6-terra-high",
        "google-gemini-3.6-flash-high",
        "google-gemini-3.7-flash-high",
    }


def test_without_vertex_or_a_key_the_roster_is_openai_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert _roster_names(monkeypatch, vertex=False) == {"openai-gpt-5.6-terra-high"}
