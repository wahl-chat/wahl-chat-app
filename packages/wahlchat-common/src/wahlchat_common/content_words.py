# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Content words of a German plenary text, for lexical overlap scoring.

Shared because two places point a reader at the sentence of a speech that a
text draws on: the chat's citation deep-links and the parliament feed's
sources per bullet and position.
"""

from __future__ import annotations

import re

# Kept small and lowercase; the > 3-char length gate already drops most
# function words, but the plenary-opener words ("damen", "herren",
# "kollegen"…) recur in every speech and would otherwise dominate the score.
_STOPWORDS = frozenset(
    {
        "damen",
        "herren",
        "kollegen",
        "kolleginnen",
        "präsident",
        "präsidentin",
        "sehr",
        "geehrte",
        "geehrter",
        "liebe",
        "meine",
        "unsere",
        "diese",
        "dieser",
        "dieses",
        "haben",
        "werden",
        "wird",
        "wurde",
        "worden",
        "einen",
        "eine",
        "einem",
        "einer",
        "auch",
        "aber",
        "nicht",
        "schon",
        "noch",
        "mehr",
        "sein",
        "sind",
        "dass",
        "denn",
        "dann",
        "hier",
        "damit",
        "durch",
        "über",
        "unter",
    }
)


def content_words(text: str) -> set[str]:
    """Lowercase content words (> 3 chars, not a stopword)."""
    return {
        w
        for w in re.findall(r"\w+", (text or "").lower())
        if len(w) > 3 and w not in _STOPWORDS
    }
