# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import pytest

from wahlchat_common.gemini_params import (
    omits_deprecated_generation_params,
    without_deprecated_generation_params,
)


@pytest.mark.parametrize(
    "model",
    [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.10-flash",
        "gemini-4-flash",
        "models/gemini-3.6-flash",
        "publishers/google/models/gemini-3.7-flash-001",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash-lite-preview",
        "gemini-3.5-flash-lite-001",
    ],
)
def test_models_that_reject_sampling(model: str) -> None:
    assert omits_deprecated_generation_params(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "gemini-3.5-flash",
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
        "gpt-5.6-terra",
    ],
)
def test_models_that_still_accept_sampling(model: str) -> None:
    assert omits_deprecated_generation_params(model) is False


def test_deprecated_params_are_removed_only_for_new_models() -> None:
    kwargs = {
        "temperature": 1.0,
        "top_p": 0.9,
        "top_k": 40,
        "thinking_budget": 0,
        "thinking_level": "minimal",
    }
    kept = without_deprecated_generation_params("gemini-3.7-flash", kwargs)
    assert kept == {"thinking_level": "minimal"}

    older = without_deprecated_generation_params("gemini-3.5-flash", kwargs)
    assert older["temperature"] == 1.0
    assert older["thinking_budget"] == 0
    assert older["thinking_level"] == "minimal"
