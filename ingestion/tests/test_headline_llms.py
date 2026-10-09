# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Generation settings on the pledge-headline roster reach the request."""

from ingestion.connectors.pledgetracker.headline_llms import pre_post_llms


def _generation_config(client) -> dict:
    config = client._build_base_generation_config(None)
    thinking = config.get("thinking_config")
    if thinking is not None:
        config = {
            **config,
            "thinking_config": thinking.model_dump(exclude_none=True),
        }
    return config


def _thinking_level(config: dict) -> str:
    level = config["thinking_config"]["thinking_level"]
    return str(getattr(level, "value", level)).lower()


def test_pre_post_roster_generation_config() -> None:
    by_name = {item.name: item.model for item in pre_post_llms()}

    lite = _generation_config(by_name["google-gemini-3.5-flash-lite"])
    assert "temperature" not in lite
    assert "top_p" not in lite
    assert "top_k" not in lite
    assert _thinking_level(lite) == "minimal"
    assert "thinking_budget" not in lite["thinking_config"]

    previous = _generation_config(by_name["google-gemini-3.1-flash-lite"])
    assert previous["temperature"] == 1.0
    assert _thinking_level(previous) == "minimal"

    oldest = _generation_config(by_name["google-gemini-2.5-flash-lite"])
    assert oldest["temperature"] == 1.0
    assert oldest["thinking_config"]["thinking_budget"] == 0
    assert "thinking_level" not in oldest["thinking_config"]
