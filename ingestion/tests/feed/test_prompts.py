# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import hashlib

from ingestion.feed.prompts import (
    _ATTRIBUTION_RULE,
    _GROUNDING_RULE,
    _NEUTRALITY_RULE,
    _POSITION_FIDELITY_RULE,
    _POSITION_SENTENCE_RULE,
    PROMPT_VERSION,
    DebateDraft,
    VoteEnrichment,
    format_debate_prompt,
    format_positions_prompt,
    format_translation_prompt,
    format_verify_prompt,
    format_vote_prompt,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_generation_prompts_are_unchanged_for_this_prompt_version() -> None:
    # The stored items were generated from exactly these prompts; a change
    # must bump PROMPT_VERSION, which regenerates them.
    assert PROMPT_VERSION == "8"
    assert (
        _sha(format_vote_prompt("Bundestag", "[V1] Antrag"))
        == "8db80234efa72878bab550b52df627fd9f9ef54d92113abe8e916bbe2d68d56c"
    )
    assert (
        _sha(
            format_debate_prompt(
                "Bundestag",
                "24.09.2026",
                "Wohnungsbau",
                "spd, cdu",
                "- Anna (spd): Wohnungen",
            )
        )
        == "759613b28644fa448de61a66f01a2e534086aa7d30fdc3598c6b3e4820c25e98"
    )
    assert (
        _sha(
            format_positions_prompt(
                "Bundestag", "Wohnungsbau", "cdu", "- Bernd (cdu): Kosten"
            )
        )
        == "c601fb27a26f7b51fb8b25b85082066a5cff80e193cbc6ce7c96cafd778bac34"
    )
    assert (
        _sha(
            format_verify_prompt(
                "Bundestag", "Wohnungsbau", "[P1] spd: Fordern mehr.", "## spd"
            )
        )
        == "5aa750787f851586f4da0ce70109b701fa8a8c115ba34ec2666ae6837414e644"
    )


def test_every_position_prompt_holds_the_same_editorial_rules() -> None:
    for prompt in (
        format_debate_prompt("Bundestag", "", "", "", ""),
        format_positions_prompt("Bundestag", "", "", ""),
    ):
        for rule in (
            _NEUTRALITY_RULE,
            _GROUNDING_RULE,
            _ATTRIBUTION_RULE,
            _POSITION_FIDELITY_RULE,
            _POSITION_SENTENCE_RULE,
        ):
            assert rule in prompt


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


def test_votes_and_debates_are_tagged_alike() -> None:
    vote = VoteEnrichment.model_fields["topics"].description
    debate = DebateDraft.model_fields["topics"].description
    assert vote == debate
    rule = "'other' nur, wenn nichts passt"
    assert rule in format_vote_prompt("Bundestag", "")
    assert rule in format_debate_prompt("Bundestag", "", "", "", "")
