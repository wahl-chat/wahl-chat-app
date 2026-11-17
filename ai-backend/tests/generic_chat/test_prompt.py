# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The rendered system prompt carries the shared rules and the language
(AC-13, AC-14)."""

from __future__ import annotations

from datetime import date

import pytest

from src.generic_chat.prompt import build_system_prompt
from src.generic_chat.schemas import AnchorContext, NumberedDocument, ToolResult
from tests.generic_chat.conftest import make_deps
from wahlchat_common.answer_rules import CITATION_RULES, VOICE_RULES, language_rule


@pytest.mark.parametrize("language", ["de", "en"])
def test_prompt_carries_rules_and_language(language: str) -> None:
    prompt = build_system_prompt(make_deps(language), today=date(2026, 11, 14))

    assert VOICE_RULES in prompt
    assert CITATION_RULES in prompt
    assert language_rule(language) in prompt  # type: ignore[arg-type]
    assert "2026-11-14 (Europe/Berlin)" in prompt


def test_prompt_rules_present() -> None:
    prompt = build_system_prompt(make_deps(), today=date(2026, 11, 14))

    assert "Never speak as a party" in prompt
    assert "wrong premise" in prompt
    assert "(nicht im Bundestag)" in prompt
    assert "preferred_outlet=false" in prompt and "not among the outlets wahl.chat prefers" in prompt
    assert "Never cite the wahl.chat feed summaries" in prompt
    assert "query it in German" in prompt
    assert "Ids start at 0" in prompt
    assert "- Volt (Volt long), id volt: not in the Bundestag" in prompt
    assert "- SPD (SPD long), id spd: in the Bundestag" in prompt
    assert "## Bezug" not in prompt


def test_prompt_names_the_anchor_and_lists_its_sources() -> None:
    deps = make_deps()
    deps.anchor = AnchorContext(
        label='vote "Mietpreisbremse" (2026-11-13)',
        result=ToolResult(
            documents=[NumberedDocument(id=0, source_type="vote_record", text="SPD: yes 120")]
        ),
    )
    prompt = build_system_prompt(deps, today=date(2026, 11, 14))
    assert '## Bezug\nThe user opened this chat from vote "Mietpreisbremse"' in prompt
    assert "not a source" in prompt
    assert '"id":0' in prompt


def test_prompt_names_the_focus_parties() -> None:
    deps = make_deps()
    deps.set_focus(["volt", "spd"])
    prompt = build_system_prompt(deps, today=date(2026, 11, 14))

    assert "## Fokus\n" in prompt
    assert "- Volt, id volt\n- SPD, id spd\n" in prompt
    assert "one short section per party" in prompt


def test_prompt_without_focus_has_no_focus_block() -> None:
    assert "## Fokus" not in build_system_prompt(make_deps(), today=date(2026, 11, 14))
