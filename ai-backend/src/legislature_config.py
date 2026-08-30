# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

# GENERATED-PAIR — duplicated in ai-backend/src/ and ingestion/src/ingestion/.
# Edit both; scripts/check_contract_parity.py enforces it.

"""AW parliament periods and term-window derivation.

The period table lives in ``corpus-contract.json``; to add a period, edit it —
no code change here. IDs were fetched once from the AW v2 API (2026-06-25) and
are never re-fetched at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from src.corpus_contract import section


@dataclass(frozen=True)
class LegislatureConfig:
    """Static config for one AW parliament period.

    Attributes:
        parliament_period_id: AW period ID (period key; also cursor scope key).
                              The dict key in LEGISLATURE_CONFIG.
        region:               ISO 3166-2 code, e.g. ``"DE-BY"`` or ``"DE"`` for federal.
        label:                AW period label, e.g. ``"Bayern 2023 - 2028"``.
        date_from:            ISO date string of period start (start_date_period).
        date_to:              ISO date string of period end (end_date_period), or None.
        wahlperiode:          German Wahlperiode number for Bundestag periods
                              (e.g. 20 for the 20th Bundestag). None for Länder —
                              state Wahlperiode ints collide across states, so
                              Landtag chunks never carry one.
    """

    parliament_period_id: int
    region: str
    label: str
    date_from: str
    date_to: Optional[str]
    wahlperiode: Optional[int] = None


LEGISLATURE_CONFIG: dict[int, LegislatureConfig] = {
    int(period_id): LegislatureConfig(
        parliament_period_id=int(period_id),
        region=row["region"],
        label=row["label"],
        date_from=row["date_from"],
        date_to=row["date_to"],
        wahlperiode=row["wahlperiode"],
    )
    for period_id, row in section("legislature_periods").items()
}

LANDTAG_LEGISLATURE_IDS: list[int] = [
    key for key, cfg in LEGISLATURE_CONFIG.items() if cfg.region != "DE"
]

# The two newest Bundestag periods — the default ingestion loop's depth, matching
# the Landtag policy. Derived, never stored in the contract: a second copy of a
# computed list is a second thing that can disagree with its source.
FEDERAL_LEGISLATURE_IDS: list[int] = [
    key
    for key, _cfg in sorted(
        ((k, c) for k, c in LEGISLATURE_CONFIG.items() if c.region == "DE"),
        key=lambda kv: kv[1].date_from,
    )[-2:]
]


# Term-window derivation for two-pass retrieval: contexts carry a region_path but
# not a date window, and this module already owns the period date ranges.

# Far-future UTC sentinel for open-ended periods (date_to is None → still current).
# Chosen as datetime.max so any real publish_date compares as "inside the window".
TERM_END_SENTINEL: datetime = datetime.max.replace(tzinfo=timezone.utc)


def _to_utc_datetime(iso: Optional[str]) -> datetime:
    """Parse an ISO date string to a tz-aware UTC datetime.

    ``None`` (open-ended period) maps to :data:`TERM_END_SENTINEL`.
    """
    if iso is None:
        return TERM_END_SENTINEL
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _row_window(cfg: LegislatureConfig) -> tuple[datetime, datetime]:
    """Return a row's (term_start, term_end) as tz-aware UTC datetimes."""
    return _to_utc_datetime(cfg.date_from), _to_utc_datetime(cfg.date_to)


def term_window_for_context(
    region_path: Optional[list[str]],
    legislature_period_id: Optional[int],
    election_date: Optional[date] = None,
) -> Optional[tuple[datetime, datetime]]:
    """Derive the ``[term_start, term_end]`` window for a chat context.

    Resolution order:
      1. If ``legislature_period_id`` names a row in :data:`LEGISLATURE_CONFIG`,
         use that row — unambiguous. Covers federal contexts and any context
         that already names its term (AW vote-record precision filter).
      2. Otherwise, if ``region_path`` is set, take the most-specific element
         (``region_path[-1]``) and gather rows whose ``region`` equals it:
           - none  → return ``None`` (caller falls back to single-pass).
           - one   → use that row.
           - many  → deterministic tiebreak (see below).

    Multi-period tiebreak (e.g. DE-BW / DE-RP, where a region has both the
    outgoing 2021–2026 term and the post-2026 term): pick the row whose
    ``[date_from, date_to]`` **contains**
    ``election_date``; else the **latest row ending on/before** ``election_date``;
    else (no ``election_date`` given, or none qualifies) the **latest row by
    date_to**. This deterministically prefers the OUTGOING term around an
    election while never returning an arbitrary row.

    Returned datetimes are tz-aware UTC; ``date_to=None`` maps to
    :data:`TERM_END_SENTINEL`. Returns ``None`` when nothing resolves.

    Pure function: no network, no Qdrant, safe to call per request.
    """
    # (1) Explicit period id — unambiguous when it is a known key.
    if legislature_period_id is not None:
        cfg = LEGISLATURE_CONFIG.get(legislature_period_id)
        if cfg is not None:
            return _row_window(cfg)
        # Unknown id: fall through to region-based resolution.

    # (2) Region-based resolution on the most-specific path element.
    if not region_path:
        return None
    local = region_path[-1]
    rows = [cfg for cfg in LEGISLATURE_CONFIG.values() if cfg.region == local]
    if not rows:
        return None
    if len(rows) == 1:
        return _row_window(rows[0])

    # Multiple periods for this region — deterministic tiebreak.
    def _start(cfg: LegislatureConfig) -> date:
        return date.fromisoformat(cfg.date_from)

    def _end(cfg: LegislatureConfig) -> date:
        return date.fromisoformat(cfg.date_to) if cfg.date_to else date.max

    if election_date is not None:
        containing = [c for c in rows if _start(c) <= election_date <= _end(c)]
        if containing:
            return _row_window(max(containing, key=_end))
        ended_before = [c for c in rows if _end(c) <= election_date]
        if ended_before:
            return _row_window(max(ended_before, key=_end))

    # Final deterministic fallback: the latest term by end date.
    return _row_window(max(rows, key=_end))
