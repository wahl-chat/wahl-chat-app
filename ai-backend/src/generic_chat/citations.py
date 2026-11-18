# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Citation numbers in a finished answer that no tool returned, and tags
like ``[procedure]`` the model writes where it has no number."""

from __future__ import annotations

import re

_ITEM = r"(?:\d+|[A-Za-z_]+)"
_CITATION = re.compile(rf"\s*\[({_ITEM}(?:\s*,\s*{_ITEM})*)\](?!\()")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?)])")


def drop_unknown_citations(text: str, known: int) -> str:
    """Remove ids outside 0..known-1 and word tags; a bracket left empty goes
    entirely. Markdown links stay."""

    def keep(match: re.Match[str]) -> str:
        ids = [n.strip() for n in match.group(1).split(",")]
        valid = [n for n in ids if n.isdigit() and int(n) < known]
        if len(valid) == len(ids):
            return match.group(0)
        if not valid:
            return ""
        lead = match.group(0)[: len(match.group(0)) - len(match.group(0).lstrip())]
        return f"{lead}[{', '.join(valid)}]"

    return _SPACE_BEFORE_PUNCT.sub(r"\1", _CITATION.sub(keep, text))
