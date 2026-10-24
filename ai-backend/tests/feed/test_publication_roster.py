# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel

import src.llms as llms
from src.feed import builder as builder_module


class Answer(BaseModel):
    text: str


def test_feed_texts_go_to_the_publication_roster_without_chat_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake(
        roster: list, messages: list, schema: type, *, report_rate_limit: bool
    ) -> tuple[Any, str]:
        seen.update(roster=roster, report_rate_limit=report_rate_limit)
        return Answer(text="ok"), "entry"

    monkeypatch.setattr(llms, "get_structured_output_with_source", fake)
    result, model = asyncio.run(builder_module._default_structured_output([], Answer))
    assert (result.text, model) == ("ok", "entry")
    assert seen["roster"] is llms.PUBLICATION_LLMS
    assert seen["report_rate_limit"] is False


def test_the_publication_roster_reasons_at_length() -> None:
    assert llms.PUBLICATION_LLMS
    for entry in llms.PUBLICATION_LLMS:
        assert "lite" not in entry.name
        effort = getattr(entry.model, "thinking_level", None) or getattr(
            entry.model, "reasoning_effort", None
        )
        assert effort == llms.PUBLICATION_THINKING == "high"


class _Failing:
    def with_structured_output(self, schema: type) -> "_Failing":
        return self

    async def ainvoke(self, messages: list) -> Any:
        raise RuntimeError("quota")


def test_an_exhausted_batch_roster_does_not_flag_the_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flagged: list[bool] = []

    async def flag() -> None:
        flagged.append(True)

    monkeypatch.setattr(llms, "handle_rate_limit_hit_for_all_llms", flag)
    roster = [
        llms.LLM.model_construct(
            name="x", model=_Failing(), priority=1, back_up_only=False
        )
    ]
    with pytest.raises(Exception, match="All LLMs failed"):
        asyncio.run(
            llms.get_structured_output_with_source(
                roster, [], Answer, report_rate_limit=False
            )
        )
    assert flagged == []
    with pytest.raises(Exception, match="All LLMs failed"):
        asyncio.run(llms.get_structured_output_with_source(roster, [], Answer))
    assert flagged == [True]
