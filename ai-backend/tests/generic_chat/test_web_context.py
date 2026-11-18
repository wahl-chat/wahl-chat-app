# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Press coverage next to our sources, behind GENERIC_CHAT_WEB_CONTEXT."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

import src.generic_chat.web_context as web_context
from src.generic_chat.schemas import ProcessResult, ProcessStep, ProcessInfo, WebResult
from tests.generic_chat.conftest import make_deps


def hit(title: str, day: str | None, snippet: str = "") -> WebResult:
    return WebResult(title=title, url=f"https://www.tagesschau.de/{title}", snippet=snippet,
                     date=day, domain="tagesschau.de", preferred=True)


def test_only_dated_coverage_naming_the_subject_stays() -> None:
    words = web_context.subject_words("Gesetz zur Reform des Nachrichtendienstrechts")
    assert words == ["nachrich"]
    kept = web_context.matching(
        [
            hit("BND bekommt neue Befugnisse", "2026-11-13", "Das Nachrichtendienstrecht …"),
            hit("Nachrichtendienste 2019", "2019-01-01"),  # too old
            hit("Haushalt", "2026-11-13", "Schuldenbremse"),  # other subject
            hit("Nachrichtendienst ohne Datum", None),
        ],
        words, date(2026, 9, 1), date(2026, 11, 27),
    )
    assert [r.title for r in kept] == ["BND bekommt neue Befugnisse"]


@pytest.fixture
def sites(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    queries: list[str] = []

    async def search_sites(query: str, domains: Any, recency: Any = None) -> Any:
        queries.append(query)
        return [hit(f"Reform {i}", "2026-11-14", "Nachrichtendienstrecht") for i in range(5)], None

    monkeypatch.setattr(web_context.web, "search_sites", search_sites)
    return queries


def _procedure() -> ProcessResult:
    return ProcessResult(
        procedure=ProcessInfo.model_construct(title="Gesetz zur Reform des Nachrichtendienstrechts"),
        steps=[ProcessStep.model_construct(date="2026-09-24"), ProcessStep.model_construct(date="2026-11-13")],
    )


async def test_off_by_default_nothing_is_fetched(sites: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(web_context.ENV, raising=False)
    result = _procedure()
    await web_context.add_press(make_deps(), result)
    assert sites == [] and result.documents == []


async def test_on_a_procedure_brings_three_press_documents_once(
    sites: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(web_context.ENV, "on")
    deps = make_deps()
    first, again = _procedure(), _procedure()
    await web_context.add_press(deps, first)
    await web_context.add_press(deps, again)
    assert len(sites) == 1
    assert [d.tier for d in first.documents] == ["press"] * 3 and again.documents == []


def test_off_the_tool_offers_no_statements_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic_ai.tools import ToolDefinition

    from src.generic_chat import agent
    from src.generic_chat.schemas import WebSearchInput

    tool = ToolDefinition(name="web_search", parameters_json_schema=WebSearchInput.model_json_schema())
    stripped = agent._without_statements(tool).parameters_json_schema["properties"]["scope"]
    assert stripped["enum"] == ["news", "civic"] and "statements" not in stripped["description"]
