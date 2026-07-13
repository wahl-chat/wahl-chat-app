# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for legislature_config.py.

Covers:
  - LANDTAG_LEGISLATURE_IDS count = 16 states + outgoing D6 rows
  - Every Landtag entry has a DE-XX region code
  - Bundestag keys 111/132/161 are present with region 'DE'
  - Every Landtag region matches region_for_period(label) from the manifesto mapper
  - Outgoing BW/RP 2021–2026 rows (D6) present with correct region/dates
  - term_window_for_context() window derivation (D5)
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.ingestion.connectors.abgeordnetenwatch.legislature_config import (
    LANDTAG_LEGISLATURE_IDS,
    LEGISLATURE_CONFIG,
    TERM_END_SENTINEL,
    LegislatureConfig,
    term_window_for_context,
)
from src.ingestion.connectors.manifestos.mappers.corpus import region_for_period


class TestLegislatureConfigShape:
    """LEGISLATURE_CONFIG structural assertions."""

    # Outgoing-term rows added for D6 (retained alongside the post-2026-election
    # rows so the two-pass split can separate them by publish_date).
    _OUTGOING_LANDTAG_IDS = (126, 127)  # BW 2021–2026, RP 2021–2026
    # Prior-term rows (pre-outgoing): votes land in the HISTORIC bucket of a 2026 chat.
    _PRIOR_LANDTAG_IDS = (105,)  # BW 2016–2021

    def test_all_16_states_represented(self) -> None:
        """Every one of the 16 German states must have at least one Landtag row."""
        regions = {LEGISLATURE_CONFIG[lid].region for lid in LANDTAG_LEGISLATURE_IDS}
        expected = {
            "DE-BW", "DE-BY", "DE-BE", "DE-BB", "DE-HB", "DE-HH", "DE-HE",
            "DE-MV", "DE-NI", "DE-NW", "DE-RP", "DE-SL", "DE-SN", "DE-ST",
            "DE-SH", "DE-TH",
        }
        assert regions == expected, (
            f"Landtag regions {regions!r} do not cover exactly the 16 states {expected!r}"
        )

    def test_landtag_legislature_ids_count(self) -> None:
        """LANDTAG_LEGISLATURE_IDS == 16 states + outgoing (126/127) + prior (105) rows."""
        expected_count = (
            16 + len(self._OUTGOING_LANDTAG_IDS) + len(self._PRIOR_LANDTAG_IDS)
        )
        assert len(LANDTAG_LEGISLATURE_IDS) == expected_count, (
            f"Expected {expected_count} Landtag IDs (16 states + "
            f"{len(self._OUTGOING_LANDTAG_IDS)} outgoing + "
            f"{len(self._PRIOR_LANDTAG_IDS)} prior rows), got "
            f"{len(LANDTAG_LEGISLATURE_IDS)}: {LANDTAG_LEGISLATURE_IDS}"
        )

    def test_prior_bw_row_present_and_does_not_hijack_current_window(self) -> None:
        """The prior BW 2016–2021 row (105) exists with correct region/dates, is a
        Landtag id, and does NOT hijack the CURRENT window for a 2026 BW chat — the
        election-date 'containing' tiebreak must still resolve to the outgoing 126 term."""
        assert 105 in LANDTAG_LEGISLATURE_IDS
        cfg = LEGISLATURE_CONFIG[105]
        assert cfg.region == "DE-BW"
        assert cfg.date_from == "2016-05-11"
        assert cfg.date_to == "2021-05-10"
        # DE-BW now has three periods (105, 126, 165); the 2026 election date sits inside
        # the outgoing 126 term, so the current window must still be 2021-05-11..2026-05-11.
        window = term_window_for_context(["DE", "DE-BW"], None, date(2026, 3, 8))
        assert window is not None
        assert window[0] == datetime(2021, 5, 11, tzinfo=timezone.utc)
        assert window[1] == datetime(2026, 5, 11, tzinfo=timezone.utc)

    def test_outgoing_bw_rp_rows_present(self) -> None:
        """The outgoing BW/RP 2021–2026 rows (D6) must be present with correct region/dates.

        Both terms coexist with the post-election 165/166 rows: outgoing 126/127
        carry the 2021–2026 voting record; 165/166 begin the 2026–2031 term.
        """
        outgoing = {
            126: ("DE-BW", "2021-05-11", "2026-05-11"),
            127: ("DE-RP", "2021-03-12", "2026-05-18"),
        }
        for lid, (region, date_from, date_to) in outgoing.items():
            assert lid in LANDTAG_LEGISLATURE_IDS, (
                f"Outgoing Landtag ID {lid} missing from LANDTAG_LEGISLATURE_IDS"
            )
            cfg = LEGISLATURE_CONFIG[lid]
            assert cfg.region == region, f"ID {lid}: region {cfg.region!r} != {region!r}"
            assert cfg.date_from == date_from, (
                f"ID {lid}: date_from {cfg.date_from!r} != {date_from!r}"
            )
            assert cfg.date_to == date_to, (
                f"ID {lid}: date_to {cfg.date_to!r} != {date_to!r}"
            )
            # Range sits within 2021–2026 (outgoing term voters want around the election).
            assert cfg.date_from.startswith("2021"), f"ID {lid} outgoing term must start in 2021"
            assert cfg.date_to.startswith("2026"), f"ID {lid} outgoing term must end in 2026"

        # Post-election rows must still be present alongside the outgoing ones.
        assert LEGISLATURE_CONFIG[165].date_from.startswith("2026")
        assert LEGISLATURE_CONFIG[166].date_from.startswith("2026")

    def test_all_landtag_regions_are_de_xx(self) -> None:
        """Every Landtag entry must have a DE-XX ISO 3166-2 state region code."""
        bad = [
            lid
            for lid in LANDTAG_LEGISLATURE_IDS
            if not LEGISLATURE_CONFIG[lid].region.startswith("DE-")
        ]
        assert not bad, (
            f"Landtag IDs with non-DE-XX region: {bad!r} — "
            "each Landtag must have a region code like 'DE-BY', not 'DE'"
        )

    def test_bundestag_keys_present(self) -> None:
        """LEGISLATURE_CONFIG must contain Bundestag period IDs 111, 132, and 161."""
        for expected_key in (111, 132, 161):
            assert expected_key in LEGISLATURE_CONFIG, (
                f"Bundestag key {expected_key} missing from LEGISLATURE_CONFIG"
            )

    def test_bundestag_regions_are_de(self) -> None:
        """Bundestag entries 111/132/161 must have region 'DE' (not 'DE-*')."""
        for kid in (111, 132, 161):
            assert LEGISLATURE_CONFIG[kid].region == "DE", (
                f"Bundestag key {kid} has region {LEGISLATURE_CONFIG[kid].region!r}, "
                "expected 'DE'"
            )

    def test_all_landtag_regions_match_region_for_period(self) -> None:
        """Every Landtag row's stored region must equal region_for_period(row.label).

        This ensures the manifesto-connector region derivation function is the source
        of truth and the config values are not independently diverged.
        """
        mismatches: list[str] = []
        for lid in LANDTAG_LEGISLATURE_IDS:
            cfg = LEGISLATURE_CONFIG[lid]
            derived = region_for_period(cfg.label)
            if derived != cfg.region:
                mismatches.append(
                    f"ID={lid} label={cfg.label!r}: "
                    f"stored={cfg.region!r}, region_for_period()={derived!r}"
                )
        assert not mismatches, (
            "region_for_period(label) mismatch in LEGISLATURE_CONFIG:\n"
            + "\n".join(mismatches)
        )

    def test_legislature_config_config_dataclass_is_frozen(self) -> None:
        """LegislatureConfig must be a frozen dataclass (immutable config)."""
        cfg = LEGISLATURE_CONFIG[149]  # Bayern — guaranteed to exist
        try:
            cfg.region = "XX"  # type: ignore[misc]
            raise AssertionError("LegislatureConfig.region must be read-only (frozen=True)")
        except (AttributeError, TypeError):
            pass  # expected: frozen dataclass raises on assignment

    def test_all_landtag_ids_in_legislature_config(self) -> None:
        """Every ID in LANDTAG_LEGISLATURE_IDS must be a key in LEGISLATURE_CONFIG."""
        missing = [lid for lid in LANDTAG_LEGISLATURE_IDS if lid not in LEGISLATURE_CONFIG]
        assert not missing, (
            f"LANDTAG_LEGISLATURE_IDS contains IDs not in LEGISLATURE_CONFIG: {missing!r}"
        )


class TestTermWindowForContext:
    """term_window_for_context() term-window derivation (D5)."""

    def test_window_by_period_id(self) -> None:
        """An explicit legislature_period_id resolves that row's (date_from, date_to)."""
        window = term_window_for_context(
            region_path=["DE"], legislature_period_id=161
        )
        assert window is not None
        start, end = window
        assert start == datetime(2025, 3, 25, tzinfo=timezone.utc)
        assert end == datetime(2029, 2, 22, tzinfo=timezone.utc)

    def test_window_by_region_single(self) -> None:
        """A region with exactly one period resolves that window (no period id)."""
        # Bayern (DE-BY) has a single row: 149 Bayern 2023 - 2028.
        window = term_window_for_context(
            region_path=["DE", "DE-BY"], legislature_period_id=None
        )
        assert window is not None
        start, end = window
        assert start == datetime(2023, 10, 26, tzinfo=timezone.utc)
        assert end == datetime(2028, 10, 31, tzinfo=timezone.utc)

    def test_window_by_region_multi_picks_outgoing(self) -> None:
        """A multi-period region picks the OUTGOING term for an election on/before 2026.

        DE-BW now has two rows (126 outgoing 2021–2026, 165 post-election 2026–2031).
        For an election_date inside the outgoing term, the helper must return the
        outgoing window, not the post-election one.
        """
        window = term_window_for_context(
            region_path=["DE", "DE-BW"],
            legislature_period_id=None,
            election_date=date(2026, 3, 8),
        )
        assert window is not None
        start, end = window
        assert start == datetime(2021, 5, 11, tzinfo=timezone.utc)
        assert end == datetime(2026, 5, 11, tzinfo=timezone.utc)

    def test_window_multi_no_election_date_picks_latest(self) -> None:
        """With no election_date, a multi-period region deterministically picks
        the latest term by end date (final documented fallback branch)."""
        window = term_window_for_context(
            region_path=["DE", "DE-BW"],
            legislature_period_id=None,
            election_date=None,
        )
        assert window is not None
        start, end = window
        # Latest DE-BW term by end date is the post-election 165 (2026–2031).
        assert start == datetime(2026, 5, 12, tzinfo=timezone.utc)
        assert end == datetime(2031, 5, 20, tzinfo=timezone.utc)

    def test_window_none_when_unresolved(self) -> None:
        """Unknown region / general context with no matching row returns None."""
        assert term_window_for_context(
            region_path=["DE", "DE-XX"], legislature_period_id=None
        ) is None
        assert term_window_for_context(
            region_path=None, legislature_period_id=None
        ) is None
        # Unknown period id with no region falls through to None.
        assert term_window_for_context(
            region_path=None, legislature_period_id=999999
        ) is None

    def test_window_datetimes_are_tz_aware(self) -> None:
        """Returned datetimes carry tzinfo=UTC; date_to=None maps to the sentinel."""
        window = term_window_for_context(
            region_path=["DE"], legislature_period_id=161
        )
        assert window is not None
        start, end = window
        assert start.tzinfo == timezone.utc
        assert end.tzinfo == timezone.utc

    def test_window_open_ended_maps_to_sentinel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A row with date_to=None maps its term_end to the far-future UTC sentinel."""
        monkeypatch.setitem(
            LEGISLATURE_CONFIG,
            900001,
            LegislatureConfig(900001, "DE-ZZ", "Testland 2020 - open", "2020-01-01", None),
        )
        window = term_window_for_context(
            region_path=["DE", "DE-ZZ"], legislature_period_id=900001
        )
        assert window is not None
        start, end = window
        assert start == datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert end == TERM_END_SENTINEL
        assert end.tzinfo == timezone.utc
