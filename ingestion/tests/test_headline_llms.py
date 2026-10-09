# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The pledge-headline roster must match the chat pre/post generation settings.

Ingestion cannot import the chat service, so the constructor guard is the
only thing keeping a copied ``temperature`` off a Gemini 3.6+ request.
"""

from ingestion.connectors.pledgetracker.headline_llms import _gemini


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


def test_flash_lite_roster_omits_deprecated_sampling() -> None:
    current = _gemini("gemini-3.5-flash-lite", thinking_level="minimal")
    config = _generation_config(current)
    assert "temperature" not in config
    assert _thinking_level(config) == "minimal"
    assert "thinking_budget" not in config["thinking_config"]

    older = _gemini("gemini-2.5-flash-lite", temperature=1.0, thinking_budget=0)
    older_config = _generation_config(older)
    assert older_config["temperature"] == 1.0
    assert older_config["thinking_config"]["thinking_budget"] == 0


def test_constructor_drops_deprecated_params_for_gemini_3_7() -> None:
    client = _gemini(
        "gemini-3.7-flash",
        temperature=1.0,
        top_p=0.9,
        top_k=40,
        thinking_budget=128,
        thinking_level="low",
    )
    config = _generation_config(client)
    assert "temperature" not in config
    assert "top_p" not in config
    assert "top_k" not in config
    assert _thinking_level(config) == "low"
    assert "thinking_budget" not in config["thinking_config"]
