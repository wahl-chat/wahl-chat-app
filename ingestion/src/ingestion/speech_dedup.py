# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared speech-dedup constants and helpers — imported by BOTH speech connectors
(``bundestag_speeches``, ``openparliament_tv``) and the op supersede module, NOT
owned by either. They live in one shared module so there is a SINGLE definition:
a drift between copies would silently break cross-source dedup.
"""

from __future__ import annotations

import re
from datetime import date as date_type
from datetime import timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Text-match ratio — ONE constant, two documented aliases.
#
# The op→DIP supersede pass and the DIP pre-insert resurrection guard apply the
# SAME question ("is this the same speech across sources?") from opposite
# directions, so they MUST share one threshold. The proceedings text is
# byte-identical in intent across op/DIP but ~99% identical in practice (op
# runs ~1% longer); a DIFFERENT speech by the same speaker under the same
# agenda item scores far lower (~0.3–0.6). The aliases document which policy is
# reading the value at each call site.
# ---------------------------------------------------------------------------
SPEECH_TEXT_MATCH_RATIO: float = 0.85
SUPERSEDE_TEXT_MATCH_RATIO: float = SPEECH_TEXT_MATCH_RATIO
RESURRECTION_TEXT_MATCH_RATIO: float = SPEECH_TEXT_MATCH_RATIO

# Lookback window (days) subtracted from the since-derived YYYYMMDD floor so an
# item that transiently failed (DIP) or only just aligned (op, ~3–4 weeks
# backlog) BELOW the max-external_id watermark is re-discovered on a later run.
# Shared by both speech connectors — kept equal deliberately.
LOOKBACK_DAYS: int = 60


def norm_speech_text(text: Optional[str]) -> str:
    """Lowercase, alphanumeric-only fold for order-stable cross-source text compare."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def lookback_floor(since: int, lookback_days: int = LOOKBACK_DAYS) -> int:
    """Translate a YYYYMMDD cursor into a ``since − lookback_days`` YYYYMMDD floor.

    Args:
        since:         Integer YYYYMMDD cursor e.g. 20260601.
        lookback_days: Window size (default: the shared LOOKBACK_DAYS).

    Returns:
        Integer YYYYMMDD floor e.g. 20260402 (malformed input returns ``since``
        unchanged so a bad cursor degrades to the old strict-floor behavior).
    """
    s = str(since)
    try:
        cursor_date = date_type(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, IndexError):
        return since
    floored = cursor_date - timedelta(days=lookback_days)
    return int(floored.strftime("%Y%m%d"))


def datum_to_external_id(date_start: Optional[str]) -> Optional[int]:
    """Convert an ISO date/datetime string to a YYYYMMDD integer external_id.

    Accepts both DIP's bare ``"2026-06-15"`` and op's full
    ``"2023-04-28T10:12:00+02:00"`` (only the date prefix is read).

    Returns:
        Integer e.g. 20260615, or None for a missing/malformed input.
    """
    iso = str(date_start or "")[:10]
    try:
        return int(iso.replace("-", ""))
    except ValueError:
        return None
