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
