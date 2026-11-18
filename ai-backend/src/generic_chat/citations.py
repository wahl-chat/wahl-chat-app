# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Citation numbers in a finished answer that no tool returned."""

from __future__ import annotations

import re

_CITATION = re.compile(r"\s*\[(\d+(?:\s*,\s*\d+)*)\](?!\()")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?)])")


def drop_unknown_citations(text: str, known: int) -> str:
    """Remove ids outside 0..known-1; a bracket left empty goes entirely."""

    def keep(match: re.Match[str]) -> str:
        ids = [n.strip() for n in match.group(1).split(",")]
        valid = [n for n in ids if int(n) < known]
        if len(valid) == len(ids):
            return match.group(0)
        if not valid:
            return ""
        lead = match.group(0)[: len(match.group(0)) - len(match.group(0).lstrip())]
        return f"{lead}[{', '.join(valid)}]"

    return _SPACE_BEFORE_PUNCT.sub(r"\1", _CITATION.sub(keep, text))
