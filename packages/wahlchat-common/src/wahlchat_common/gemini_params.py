# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Generation parameters that Gemini 3.6 and later reject.

The API rejects temperature, top_p, top_k, and thinking_budget.
Gemini 3.5 Flash-Lite uses this rule. gemini-3.5-flash does not.
Do not use only the version number.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# The API rejects these fields. Use thinking_level.
DEPRECATED_GENERATION_PARAMS = ("temperature", "top_p", "top_k", "thinking_budget")

# Vertex appends a revision, for example gemini-3.6-flash-001.
_REVISION_SUFFIX = re.compile(r"-\d{3}$")
_GEMINI_VERSION = re.compile(r"^gemini-(\d+)(?:\.(\d+))?")

_EARLY_FIXED_SAMPLING_PREFIX = "gemini-3.5-flash-lite"


def gemini_model_id(model: str) -> str:
    name = model.strip().lower().rsplit("/", 1)[-1]
    return _REVISION_SUFFIX.sub("", name)


def omits_deprecated_generation_params(model: str) -> bool:
    model_id = gemini_model_id(model)
    if model_id == _EARLY_FIXED_SAMPLING_PREFIX or model_id.startswith(
        _EARLY_FIXED_SAMPLING_PREFIX + "-"
    ):
        return True
    match = _GEMINI_VERSION.match(model_id)
    if match is None:
        return False
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return (major, minor) >= (3, 6)


def without_deprecated_generation_params(
    model: str, kwargs: Mapping[str, Any]
) -> dict[str, Any]:
    if not omits_deprecated_generation_params(model):
        return dict(kwargs)
    return {
        key: value
        for key, value in kwargs.items()
        if key not in DEPRECATED_GENERATION_PARAMS
    }
