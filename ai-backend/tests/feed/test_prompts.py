# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import hashlib

from src.feed.prompts import (
    _ATTRIBUTION_RULE,
    _GROUNDING_RULE,
    _NEUTRALITY_RULE,
    _POSITION_SENTENCE_RULE,
    PROMPT_VERSION,
    format_session_prompt,
    format_translation_prompt,
    format_vote_prompt,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_generation_prompts_are_unchanged_for_this_prompt_version() -> None:
    # The stored days were generated from exactly these prompts; a change
    # must bump PROMPT_VERSION, which regenerates them.
    assert PROMPT_VERSION == "6"
    assert (
        _sha(format_vote_prompt("Bundestag", "[V1] Antrag"))
        == "8db80234efa72878bab550b52df627fd9f9ef54d92113abe8e916bbe2d68d56c"
    )
    assert (
        _sha(format_session_prompt("Bundestag", "24.09.2026", "[A1] Wohnungsbau"))
        == "34211354c0a8a35e204a5e44f36b2c79a78e99536d67bfdaca8bb910c277a58a"
    )


def test_translation_is_held_to_the_same_editorial_rules() -> None:
    prompt = format_translation_prompt("Bundestag", "[I1]\nheadline: Test")
    for rule in (
        _NEUTRALITY_RULE,
        _GROUNDING_RULE,
        _ATTRIBUTION_RULE,
        _POSITION_SENTENCE_RULE,
    ):
        assert rule in prompt
    assert "neutrale Übersicht" in prompt
    assert prompt.endswith("[I1]\nheadline: Test\n")
