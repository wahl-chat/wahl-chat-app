# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Generation settings on the pledge-headline roster reach the request."""

from typing import Any

import pytest

from ingestion.connectors.pledgetracker import headline_llms
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


def _roster_names(monkeypatch: pytest.MonkeyPatch) -> set[str]:
    real = headline_llms._gemini

    def gemini(model: str, *, vertex: bool = False, **kwargs: Any) -> Any:
        # Only the Vertex client is faked (it needs real credentials); an AI
        # Studio client is built for real, so building one without a key fails.
        return object() if vertex else real(model, vertex=vertex, **kwargs)

    monkeypatch.setattr(headline_llms, "vertex_enabled", lambda: True)
    monkeypatch.setattr(headline_llms, "vertex_project", lambda: "project")
    monkeypatch.setattr(headline_llms, "_gemini", gemini)
    return {entry.name for entry in headline_llms._build_pre_post_llms()}


def test_the_headline_roster_runs_on_vertex_without_an_ai_studio_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert _roster_names(monkeypatch) == {
        "vertex-gemini-3.1-flash-lite",
        "vertex-gemini-3.5-flash-lite",
        "openai-gpt-5.6-luna",
    }


def test_ai_studio_joins_the_headline_roster_when_a_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "key")
    assert _roster_names(monkeypatch) >= {
        "google-gemini-3.1-flash-lite",
        "google-gemini-3.5-flash-lite",
    }
