# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Versioned configuration for all supported AW parliament periods.

IDs were fetched once from the AW v2 API (2026-06-25) via:
  GET /parliaments  → 18 parliaments (Bundestag, EU-Parlament, 16 Landtage)
  GET /parliament-periods?parliament={id}&type=legislature
  → selected current period (most recent end_date_period > 2026-06-25)

These IDs are authoritative and never re-fetched at runtime.  To add a prior
period or a newly created Landtag period, add a row and increment nothing else.

All IDs are VERIFIED from the AW v2 public CC0 API.

Key:   parliament_period_id (AW integer — the dict key used by
       ``field_legislature`` in the polls endpoint; globally unique).
       This is also the value stamped as ``legislature_period_id`` on every
       vote_record ChunkRecord.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional


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


# ---------------------------------------------------------------------------
# LEGISLATURE_CONFIG — single source of truth for all supported legislatures.
#
# To add a prior legislature period: add a row here. No other code change needed.
# To add a new Landtag election: add the new parliament_period row from the AW API
# (GET /parliament-periods?parliament={parl_id}&type=legislature) and update
# the existing row's date_to to the end_date_period of the outgoing period.
# ---------------------------------------------------------------------------
LEGISLATURE_CONFIG: dict[int, LegislatureConfig] = {
    # -----------------------------------------------------------------------
    # Bundestag — wahlperiode is the sole source of the Wahlperiode number.
    # Verified: AW API parliament-periods/{id} (2026-06-25)
    # -----------------------------------------------------------------------
    111: LegislatureConfig(
        111, "DE", "Bundestag 2017 - 2021", "2017-10-24", "2021-10-25", wahlperiode=19
    ),
    132: LegislatureConfig(
        132, "DE", "Bundestag 2021 - 2025", "2021-10-26", "2025-03-24", wahlperiode=20
    ),
    161: LegislatureConfig(
        161, "DE", "Bundestag 2025 - 2029", "2025-03-25", "2029-02-22", wahlperiode=21
    ),
    # -----------------------------------------------------------------------
    # Landtage — current legislature period each (IDs VERIFIED from AW API, 2026-06-25).
    # region derived via region_for_period(label) from manifestos/mappers/corpus.py.
    # Sorted by AW parliament ID for readability.
    # -----------------------------------------------------------------------
    # Berlin (parliament_id=2)
    133: LegislatureConfig(
        133, "DE-BE", "Berlin 2021 - 2026", "2021-10-04", "2026-10-25"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=2&type=legislature) 2026-07-24.
    107: LegislatureConfig(
        107, "DE-BE", "Berlin 2016 - 2021", "2016-10-27", "2021-10-03"
    ),
    # Hamburg (parliament_id=3)
    162: LegislatureConfig(
        162, "DE-HH", "Hamburg 2025 - 2029", "2025-03-26", "2029-05-03"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=3&type=legislature) 2026-07-24.
    122: LegislatureConfig(
        122, "DE-HH", "Hamburg 2020 - 2025", "2020-03-18", "2025-03-25"
    ),
    # Nordrhein-Westfalen (parliament_id=4)
    139: LegislatureConfig(
        139, "DE-NW", "Nordrhein-Westfalen 2022 - 2027", "2022-06-01", "2027-05-30"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=4&type=legislature) 2026-07-24.
    109: LegislatureConfig(
        109, "DE-NW", "Nordrhein-Westfalen 2017 - 2022", "2017-06-01", "2022-05-31"
    ),
    # Baden-Württemberg (parliament_id=6)
    165: LegislatureConfig(
        165, "DE-BW", "Baden-Württemberg 2026 - 2031", "2026-05-12", "2031-05-20"
    ),
    # OUTGOING term: the 2021–2026 legislature whose voting record voters want
    # around the 2026 election. Retained ALONGSIDE 165 so the two-pass split can
    # separate them by publish_date. IDs/dates VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=6&type=legislature) 2026-07-09.
    126: LegislatureConfig(
        126, "DE-BW", "Baden-Württemberg 2021 - 2026", "2021-05-11", "2026-05-11"
    ),
    # PRIOR term (pre-outgoing): votes here have publish_date < 2021-05-11, so they land
    # in the HISTORIC bucket of a 2026 BW chat (the election-date "containing" tiebreak
    # still resolves the CURRENT window to the outgoing 126 term). IDs/dates VERIFIED from
    # AW v2 CC0 API (GET /parliament-periods?parliament=6&type=legislature) 2026-07-09.
    105: LegislatureConfig(
        105, "DE-BW", "Baden-Württemberg 2016 - 2021", "2016-05-11", "2021-05-10"
    ),
    # Rheinland-Pfalz (parliament_id=7)
    166: LegislatureConfig(
        166, "DE-RP", "Rheinland-Pfalz 2026 - 2031", "2026-05-18", "2031-05-31"
    ),
    # OUTGOING term: the 2021–2026 legislature retained for pre/around-election
    # voting-record retrieval, alongside the post-election 166. IDs/dates VERIFIED
    # from AW v2 CC0 API (GET /parliament-periods?parliament=7&type=legislature) 2026-07-09.
    127: LegislatureConfig(
        127, "DE-RP", "Rheinland-Pfalz 2021 - 2026", "2021-03-12", "2026-05-18"
    ),
    # Sachsen-Anhalt (parliament_id=8)
    131: LegislatureConfig(
        131, "DE-ST", "Sachsen-Anhalt 2021 - 2026", "2021-07-06", "2026-10-06"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=8&type=legislature) 2026-07-24.
    114: LegislatureConfig(
        114, "DE-ST", "Sachsen-Anhalt 2016 - 2021", "2016-04-12", "2021-07-05"
    ),
    # Mecklenburg-Vorpommern (parliament_id=9)
    134: LegislatureConfig(
        134, "DE-MV", "Mecklenburg-Vorpommern 2021 - 2026", "2021-10-26", "2026-10-25"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=9&type=legislature) 2026-07-24.
    108: LegislatureConfig(
        108, "DE-MV", "Mecklenburg-Vorpommern 2016 - 2021", "2016-10-04", "2021-10-25"
    ),
    # Bremen (parliament_id=10)
    146: LegislatureConfig(
        146, "DE-HB", "Bremen 2023 - 2027", "2023-06-29", "2027-06-01"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=10&type=legislature) 2026-07-24.
    118: LegislatureConfig(
        118, "DE-HB", "Bremen 2019 - 2023", "2019-07-03", "2023-06-28"
    ),
    # Hessen (parliament_id=11)
    150: LegislatureConfig(
        150, "DE-HE", "Hessen 2024 - 2029", "2024-01-18", "2029-01-31"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=11&type=legislature) 2026-07-24.
    116: LegislatureConfig(
        116, "DE-HE", "Hessen 2019 - 2024", "2019-01-18", "2024-01-17"
    ),
    # Niedersachsen (parliament_id=12)
    143: LegislatureConfig(
        143, "DE-NI", "Niedersachsen 2022 - 2027", "2022-11-08", "2027-11-18"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=12&type=legislature) 2026-07-24.
    112: LegislatureConfig(
        112, "DE-NI", "Niedersachsen 2017 - 2022", "2017-11-14", "2022-11-07"
    ),
    # Bayern (parliament_id=13) — empirical check confirmed ~149
    149: LegislatureConfig(
        149, "DE-BY", "Bayern 2023 - 2028", "2023-10-26", "2028-10-31"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=13&type=legislature) 2026-07-24.
    115: LegislatureConfig(
        115, "DE-BY", "Bayern 2018 - 2023", "2018-11-02", "2023-10-25"
    ),
    # Saarland (parliament_id=14)
    137: LegislatureConfig(
        137, "DE-SL", "Saarland 2022 - 2027", "2022-04-25", "2027-03-27"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=14&type=legislature) 2026-07-24.
    113: LegislatureConfig(
        113, "DE-SL", "Saarland 2017 - 2022", "2017-04-25", "2022-04-24"
    ),
    # Thüringen (parliament_id=15)
    156: LegislatureConfig(
        156, "DE-TH", "Thüringen 2024 - 2029", "2024-09-26", "2029-09-30"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=15&type=legislature) 2026-07-24.
    121: LegislatureConfig(
        121, "DE-TH", "Thüringen 2019 - 2024", "2019-11-26", "2024-09-26"
    ),
    # Brandenburg (parliament_id=16)
    158: LegislatureConfig(
        158, "DE-BB", "Brandenburg 2024 - 2029", "2024-10-17", "2029-10-22"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=16&type=legislature) 2026-07-24.
    120: LegislatureConfig(
        120, "DE-BB", "Brandenburg 2019 - 2024", "2019-09-02", "2024-10-16"
    ),
    # Sachsen (parliament_id=17)
    157: LegislatureConfig(
        157, "DE-SN", "Sachsen 2024 - 2029", "2024-10-01", "2029-09-30"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=17&type=legislature) 2026-07-24.
    119: LegislatureConfig(
        119, "DE-SN", "Sachsen 2019 - 2024", "2019-10-01", "2024-09-30"
    ),
    # Schleswig-Holstein (parliament_id=18)
    138: LegislatureConfig(
        138, "DE-SH", "Schleswig-Holstein 2022 - 2027", "2022-06-07", "2027-05-30"
    ),
    # Prior term. VERIFIED from AW v2 CC0 API
    # (GET /parliament-periods?parliament=18&type=legislature) 2026-07-24.
    110: LegislatureConfig(
        110, "DE-SH", "Schleswig-Holstein 2017 - 2022", "2017-06-06", "2022-06-06"
    ),
}

# ---------------------------------------------------------------------------
# LANDTAG_LEGISLATURE_IDS — all Landtag parliament_period IDs.
# Derived from LEGISLATURE_CONFIG: any entry with region != "DE" is a Landtag.
# Includes the OUTGOING BW/RP 2021–2026 terms (126/127) alongside
# the post-election 165/166 rows. Currently consumed by tests; an operator
# ingesting all Landtage runs the connector once per id (AW_LEGISLATURE_ID).
# ---------------------------------------------------------------------------
LANDTAG_LEGISLATURE_IDS: list[int] = [
    key for key, cfg in LEGISLATURE_CONFIG.items() if cfg.region != "DE"
]

# ---------------------------------------------------------------------------
# FEDERAL_LEGISLATURE_IDS — the Bundestag periods the default ingestion loop
# runs: CURRENT + PRIOR (the two newest region-"DE" rows by date_from),
# matching the Landtag depth policy. Derived from LEGISLATURE_CONFIG so the
# Makefile loop can never drift from the config; the connector requires an
# explicit AW_LEGISLATURE_ID, so a silent lone-default period cannot recur.
# Older configured periods (e.g. the 19th Bundestag row, which also anchors
# the golden test fixtures) stay runnable via an explicit AW_LEGISLATURE_ID
# but are NOT part of the default corpus.
# ---------------------------------------------------------------------------
FEDERAL_LEGISLATURE_IDS: list[int] = [
    key
    for key, _cfg in sorted(
        ((k, c) for k, c in LEGISLATURE_CONFIG.items() if c.region == "DE"),
        key=lambda kv: kv[1].date_from,
    )[-2:]
]


# ---------------------------------------------------------------------------
# Term-window derivation.
#
# The two-pass temporal retrieval needs a concrete [term_start, term_end]
# window per chat context to split "current" (publish_date inside the window)
# from "historic" (publish_date before it). State contexts carry a region_path
# but NOT the window.
#
# WHY derive from this config instead of stamping the window on ``Context``:
#   - ``Context`` is a broad, cross-cutting schema; adding a term window there
#     couples every caller to a temporal concept only retrieval needs.
#   - This module is already the single source of truth for period date ranges,
#     so deriving here keeps one authority for "what dates does term X span".
#   - The helper is pure (no network, no Qdrant), cheap to call per request
#     (an in-memory scan over ~20 rows), and trivially unit-testable.
# ---------------------------------------------------------------------------

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
