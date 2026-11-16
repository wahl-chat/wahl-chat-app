# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Bundestag Drucksache numbers as ``"{wp}/{number}"``, read from text or links."""

from __future__ import annotations

import re
from collections.abc import Iterable

# "21/6130" as the protocol prints it.
_DRUCKSACHE_TEXT = re.compile(r"\b(\d{2})/(\d{1,5})\b")
# The PDF of Drucksache 21/6130: dserver.bundestag.de/btd/21/061/2106130.pdf
_DRUCKSACHE_PDF = re.compile(
    r"dserver\.bundestag\.de/btd/(\d{2})/\d{3}/(\d{2})(\d{5})\.pdf"
)

def _sorted(ids: Iterable[tuple[int, int]]) -> list[str]:
    return [f"{wp}/{number}" for wp, number in sorted(set(ids))]


def drucksachen_in_text(text: str) -> list[str]:
    return _sorted(
        (int(wp), int(number)) for wp, number in _DRUCKSACHE_TEXT.findall(text)
    )


def drucksachen_in_links(html: str) -> list[str]:
    """The Drucksachen an HTML text links to, by their PDF on dserver."""
    return _sorted(
        (int(wp), int(number))
        for wp, file_wp, number in _DRUCKSACHE_PDF.findall(html)
        if wp == file_wp
    )
