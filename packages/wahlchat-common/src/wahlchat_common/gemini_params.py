# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Generation parameters newer Gemini models will accept.

Starting with Gemini 3.6, a request that sets ``temperature``, ``top_p``,
``top_k``, or ``thinking_budget`` is rejected. Gemini 3.5 Flash-Lite adopted
the same rules one release early. Plain ``gemini-3.5-flash`` did not, so a
version comparison alone would retire sampling on a model that still honors it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# Keys Google errors on for Gemini 3.6 and later. ``thinking_level`` replaces
# ``thinking_budget``; sampling is left at the model default.
DEPRECATED_GENERATION_PARAMS = ("temperature", "top_p", "top_k", "thinking_budget")

# Vertex sometimes publishes a model as ``gemini-3.6-flash-001``.
_REVISION_SUFFIX = re.compile(r"-\d{3}$")
_GEMINI_VERSION = re.compile(r"^gemini-(\d+)(?:\.(\d+))?")

# Exact ids, plus any later suffix (``-preview``, a Vertex revision already
# stripped). ``gemini-3.5-flash`` must not match.
_EARLY_FIXED_SAMPLING_PREFIX = "gemini-3.5-flash-lite"


def gemini_model_id(model: str) -> str:
    """Model id without a publisher path or a trailing Vertex revision."""
    name = model.strip().lower().rsplit("/", 1)[-1]
    return _REVISION_SUFFIX.sub("", name)


def omits_deprecated_generation_params(model: str) -> bool:
    """Whether ``model`` rejects custom sampling and ``thinking_budget``."""
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
    """Drop parameters ``model`` would reject.

    Older models are returned unchanged, including an explicit ``temperature``.
    """
    if not omits_deprecated_generation_params(model):
        return dict(kwargs)
    return {
        key: value
        for key, value in kwargs.items()
        if key not in DEPRECATED_GENERATION_PARAMS
    }
