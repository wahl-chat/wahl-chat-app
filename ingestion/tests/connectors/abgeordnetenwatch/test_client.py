# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for AWClient — covers the rate ceiling and core invariants.

Tests defined here:
  - test_get_sleeps_before_request: get() sleeps >=2s before each call
  - test_get_raises_on_bad_meta_status: meta.status != "ok" -> ValueError
  - test_paginates_by_row_count_without_overlap: get_all treats range_end as a
    row count and advances range_start by the delivered count (no page overlap)
  - test_get_all_stops_at_total: get_all stops when start >= total (no infinite loop)
  - test_rate_ceiling_30_per_60s: 30 sequential get() calls accumulate >=58s of
    mocked sleep (<=30 req/60s ceiling)
  - test_base_url_is_pinned_constant: _AW_BASE is the expected literal constant
  - test_get_votes_for_poll_uses_range_800: votes endpoint uses range_end=800

All tests mock time.sleep and requests.Session — NO live network calls.
The mocked-clock assertion for the rate ceiling (test_rate_ceiling_30_per_60s)
accumulates sleep calls to verify the timing contract without actually waiting.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ingestion.connectors.abgeordnetenwatch.client import AWClient, _AW_BASE


# ---------------------------------------------------------------------------
# Helpers — mock HTTP response factories
# ---------------------------------------------------------------------------


def _make_ok_response(data: Any, total: int = 1, count: int = 1) -> MagicMock:
    """Build a mock requests.Response that returns meta.status='ok'."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "meta": {
            "status": "ok",
            "status_message": "",
            "result": {
                "count": count,
                "total": total,
                "range_start": 0,
                "range_end": count,
            },
        },
        "data": data,
    }
    return resp


def _make_error_response() -> MagicMock:
    """Build a mock requests.Response with meta.status='error'."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "meta": {
            "status": "error",
            "status_message": "The following parameter(s) are not valid: parliament_period",
            "result": {"count": 0, "total": 0, "range_start": 0, "range_end": 0},
        },
        "data": [],
    }
    return resp


# ---------------------------------------------------------------------------
# Base URL constant — SSRF guard
# ---------------------------------------------------------------------------


class TestBaseUrlConstant:
    def test_aw_base_is_pinned(self) -> None:
        """_AW_BASE must be the exact pinned AW v2 URL (SSRF guard)."""
        assert _AW_BASE == "https://www.abgeordnetenwatch.de/api/v2"

    def test_aw_base_contains_abgeordnetenwatch(self) -> None:
        """_AW_BASE contains the expected domain fragment."""
        assert "abgeordnetenwatch.de/api/v2" in _AW_BASE


# ---------------------------------------------------------------------------
# get() — pacing + meta.status guard
# ---------------------------------------------------------------------------


class TestGet:
    def test_get_sleeps_before_request(self) -> None:
        """get() must call time.sleep() before each request (pacing)."""
        mock_resp = _make_ok_response({"id": 3602}, total=1, count=1)
        with (
            patch("time.sleep") as mock_sleep,
            patch("requests.Session.get", return_value=mock_resp),
        ):
            c = AWClient()
            c.get("polls/3602")
            assert mock_sleep.called, "time.sleep must be called before each get() call"
            # call_args_list entries are call(args, kwargs); first positional arg is [0][0]
            sleep_seconds = mock_sleep.call_args_list[0][0][0]
            assert sleep_seconds >= 2.0, f"sleep must be >=2s, got {sleep_seconds}"

    def test_get_returns_parsed_dict(self) -> None:
        """get() returns the full parsed JSON response dict."""
        mock_resp = _make_ok_response({"id": 3602}, total=1, count=1)
        with patch("time.sleep"), patch("requests.Session.get", return_value=mock_resp):
            c = AWClient()
            result = c.get("polls/3602")
        assert isinstance(result, dict)
        assert result["meta"]["status"] == "ok"
        assert result["data"] == {"id": 3602}

    def test_get_raises_on_error_status(self) -> None:
        """get() raises ValueError when meta.status != 'ok' (API error envelope guard)."""
        mock_resp = _make_error_response()
        with patch("time.sleep"), patch("requests.Session.get", return_value=mock_resp):
            c = AWClient()
            with pytest.raises(ValueError, match="AW API error"):
                c.get("polls", params={"parliament_period": 132})

    def test_get_uses_pinned_base_url(self) -> None:
        """get() constructs the URL from _AW_BASE + path, never from a caller-supplied host."""
        mock_resp = _make_ok_response([], total=0, count=0)
        captured_urls = []

        def capture_get(url: str, **kwargs: Any) -> MagicMock:
            captured_urls.append(url)
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with (
            patch("time.sleep"),
            patch("requests.Session.get", side_effect=capture_get),
        ):
            c = AWClient()
            c.get("polls/3602")

        assert len(captured_urls) == 1
        assert captured_urls[0].startswith(_AW_BASE), (
            f"URL must start with pinned _AW_BASE, got: {captured_urls[0]}"
        )
        assert captured_urls[0] == f"{_AW_BASE}/polls/3602"


# ---------------------------------------------------------------------------
# get_all() — row-count pagination
# ---------------------------------------------------------------------------


class TestGetAll:
    def test_paginates_by_row_count_without_overlap(self) -> None:
        """get_all() must treat range_end as a ROW COUNT (live AW contract).

        The mock mimics the live API — a request at range_start=N for
        range_end=K returns rows N..N+K-1 — so the old ``range_end=start+100``
        (absolute-index) assumption would re-fetch rows and duplicate them.
        get_all must request a fixed _PAGE_SIZE window and advance by the
        delivered count, so each row appears exactly once, in order.
        """
        from ingestion.connectors.abgeordnetenwatch.client import _PAGE_SIZE

        total = 250
        universe = [{"id": i} for i in range(total)]
        seen: list[tuple[int, int]] = []

        def fake_get(path: str, params: dict | None = None) -> dict:
            params = params or {}
            rs = params.get("range_start", 0)
            row_count = params.get("range_end")
            seen.append((rs, row_count))
            rows = universe[rs : rs + row_count] if row_count else universe[rs:]
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": len(rows),
                        "total": total,
                        "range_start": rs,
                        "range_end": row_count,
                    },
                },
                "data": rows,
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_all("polls", {"field_legislature": 111})

        ids = [r["id"] for r in result]
        assert ids == list(range(total)), "each row exactly once, in order"
        assert len(ids) == len(set(ids)), "no duplicates (no page overlap)"
        # range_end must be the constant page size (a row count), never start+size.
        assert all(rc == _PAGE_SIZE for _, rc in seen), (
            f"range_end must equal _PAGE_SIZE={_PAGE_SIZE}, saw {seen}"
        )
        # range_start advances by the delivered count: 0 -> 100 -> 200.
        assert [rs for rs, _ in seen] == [0, 100, 200], seen

    def test_stops_at_total(self) -> None:
        """get_all() stops when all items have been fetched (no infinite loop)."""
        data = [{"id": i} for i in range(50)]

        call_count = 0

        def fake_get(path: str, params: dict | None = None) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                raise RuntimeError(
                    "get_all made too many calls — infinite loop detected"
                )
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": 50,
                        "total": 50,
                        "range_start": 0,
                        "range_end": 50,
                    },
                },
                "data": data,
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_all("polls", {"field_legislature": 111})

        assert result == data
        assert call_count == 1, f"Expected 1 call for 50-item result, got {call_count}"

    def test_page_cap_breaks_infinite_loop(self) -> None:
        """get_all stops at _MAX_PAGES even if total is absurdly large."""
        from ingestion.connectors.abgeordnetenwatch.client import _MAX_PAGES

        call_count = 0

        def fake_get(path: str, params: dict | None = None) -> dict:
            nonlocal call_count
            call_count += 1
            rs = (params or {}).get("range_start", 0)
            # Advertise a huge total that would never be reached.
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": 100,
                        "total": 10_000_000,
                        "range_start": rs,
                        "range_end": rs + 100,
                    },
                },
                "data": [{"id": rs + i} for i in range(100)],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_all("polls", {"field_legislature": 111})

        assert call_count == _MAX_PAGES, (
            f"get_all must stop at _MAX_PAGES={_MAX_PAGES}, made {call_count} calls"
        )
        assert len(result) == _MAX_PAGES * 100

    def test_missing_meta_result_raises_value_error(self) -> None:
        """A 200-OK envelope missing meta.result.total raises ValueError, not KeyError."""

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {"meta": {"status": "ok"}, "data": []}  # no result

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            with pytest.raises(ValueError, match="missing meta.result.total"):
                c.get_all("polls", {"field_legislature": 111})

    def test_missing_data_raises_value_error(self) -> None:
        """A 200-OK envelope missing 'data' raises ValueError, not KeyError."""

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {
                "meta": {
                    "status": "ok",
                    "result": {
                        "count": 0,
                        "total": 0,
                        "range_start": 0,
                        "range_end": 100,
                    },
                }
            }  # no data key

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            with pytest.raises(ValueError, match="missing or non-list 'data'"):
                c.get_all("polls", {"field_legislature": 111})

    def test_get_all_uses_field_legislature_param(self) -> None:
        """get_all() passes field_legislature (not parliament_period) guard."""
        received_params = []

        def fake_get(path: str, params: dict | None = None) -> dict:
            received_params.append(dict(params or {}))
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": 0,
                        "total": 0,
                        "range_start": 0,
                        "range_end": 100,
                    },
                },
                "data": [],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            c.get_all("polls", {"field_legislature": 111})

        assert received_params[0].get("field_legislature") == 111, (
            "get_all must pass field_legislature (not parliament_period)"
        )

    def test_under_delivered_page_advances_by_delivered_count(self) -> None:
        """A server that caps a page below the requested window must NOT be
        skipped or raise: because get_all advances range_start by the count
        actually delivered, the extra pages collect every row (no gap, no
        duplicate) rather than striding past the tail.
        """
        total = 150
        universe = [{"id": i} for i in range(total)]
        cap = 60  # server delivers at most 60 rows per page (below _PAGE_SIZE)

        def fake_get(path: str, params: dict | None = None) -> dict:
            params = params or {}
            rs = params.get("range_start", 0)
            requested = params.get("range_end") or cap
            rows = universe[rs : rs + min(cap, requested)]
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": len(rows),
                        "total": total,
                        "range_start": rs,
                        "range_end": requested,
                    },
                },
                "data": rows,
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_all("polls", {"field_legislature": 111})

        ids = [r["id"] for r in result]
        assert ids == list(range(total)), "all rows collected once despite the cap"
        assert len(ids) == len(set(ids)), "no duplicates"

    def test_short_final_page_is_not_under_delivery(self) -> None:
        """The last page legitimately delivers total - start items (< _PAGE_SIZE)."""
        page1 = [{"id": i} for i in range(100)]
        page2 = [{"id": i} for i in range(100, 130)]  # 30 items — the true tail

        def fake_get(path: str, params: dict | None = None) -> dict:
            rs = (params or {}).get("range_start", 0)
            data = page1 if rs == 0 else page2
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": len(data),
                        "total": 130,
                        "range_start": rs,
                        "range_end": rs + 100,
                    },
                },
                "data": data,
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_all("polls", {"field_legislature": 111})
        assert len(result) == 130


# ---------------------------------------------------------------------------
# get_votes_for_poll() — single call with range_end=800
# ---------------------------------------------------------------------------


class TestGetVotesForPoll:
    def test_uses_range_end_800(self) -> None:
        """get_votes_for_poll() fetches all votes in one call with range_end=800."""
        captured_params = []

        def fake_get(path: str, params: dict | None = None) -> dict:
            captured_params.append(dict(params or {}))
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": 709,
                        "total": 709,
                        "range_start": 0,
                        "range_end": 800,
                    },
                },
                "data": [
                    {"id": i, "vote": "yes", "fraction": {"id": 22}} for i in range(709)
                ],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_votes_for_poll(3602)

        assert len(result) == 709
        assert captured_params[0].get("poll") == 3602
        assert captured_params[0].get("range_start") == 0
        assert captured_params[0].get("range_end") == 800

    def test_returns_only_data_list(self) -> None:
        """get_votes_for_poll() returns the data list, not the full response envelope."""
        vote_data = [{"id": 1, "vote": "yes", "fraction": {"id": 22}}]

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": 1,
                        "total": 1,
                        "range_start": 0,
                        "range_end": 800,
                    },
                },
                "data": vote_data,
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_votes_for_poll(3602)

        assert result == vote_data

    def test_raises_when_total_exceeds_window(self) -> None:
        """A poll with >800 total votes raises instead of silently truncating."""

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    # total exceeds the 800-vote single-call window.
                    "result": {
                        "count": 800,
                        "total": 950,
                        "range_start": 0,
                        "range_end": 800,
                    },
                },
                "data": [
                    {"id": i, "vote": "yes", "fraction": {"id": 22}} for i in range(800)
                ],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            with pytest.raises(ValueError, match="exceeding the single-call window"):
                c.get_votes_for_poll(4242)

    def test_total_equal_to_window_does_not_raise(self) -> None:
        """Exactly _VOTES_RANGE_END votes is within the window (no raise)."""
        from ingestion.connectors.abgeordnetenwatch.client import _VOTES_RANGE_END

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": _VOTES_RANGE_END,
                        "total": _VOTES_RANGE_END,
                        "range_start": 0,
                        "range_end": _VOTES_RANGE_END,
                    },
                },
                "data": [
                    {"id": i, "vote": "yes", "fraction": {"id": 22}}
                    for i in range(_VOTES_RANGE_END)
                ],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            result = c.get_votes_for_poll(3602)
        assert len(result) == _VOTES_RANGE_END

    def test_raises_on_under_delivery(self) -> None:
        """total says 709 but only 100 votes returned → raise (would corrupt tallies)."""

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {
                "meta": {
                    "status": "ok",
                    "status_message": "",
                    "result": {
                        "count": 100,
                        "total": 709,
                        "range_start": 0,
                        "range_end": 800,
                    },
                },
                "data": [
                    {"id": i, "vote": "yes", "fraction": {"id": 22}} for i in range(100)
                ],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            with pytest.raises(ValueError, match="expected 709 votes but received 100"):
                c.get_votes_for_poll(3602)

    def test_raises_on_missing_total(self) -> None:
        """A missing/non-int meta.result.total raises rather than bypassing the guards."""

        def fake_get(path: str, params: dict | None = None) -> dict:
            return {
                "meta": {"status": "ok", "status_message": "", "result": {"count": 1}},
                "data": [{"id": 1, "vote": "yes", "fraction": {"id": 22}}],
            }

        c = AWClient()
        with patch.object(c, "get", side_effect=fake_get):
            with pytest.raises(ValueError, match="missing/non-int"):
                c.get_votes_for_poll(3602)


# ---------------------------------------------------------------------------
# Rate ceiling
# ---------------------------------------------------------------------------


class TestRateCeiling:
    def test_30_calls_accumulate_at_least_58s(self) -> None:
        """30 sequential get() calls must accumulate >=58s of sleep (<=30 req/60s).

        Mocked-clock assertion: time.sleep is replaced with an accumulator.
        No live network call is made — requests.Session.get is also mocked.
        This asserts the rate-ceiling contract without actually waiting 60s.
        """
        mock_resp = _make_ok_response({"id": 1}, total=1, count=1)
        total_slept = 0.0

        def accumulate_sleep(seconds: float) -> None:
            nonlocal total_slept
            total_slept += seconds

        with (
            patch("time.sleep", side_effect=accumulate_sleep),
            patch("requests.Session.get", return_value=mock_resp),
        ):
            c = AWClient()
            for _ in range(30):
                c.get("polls/3602")

        assert total_slept >= 58.0, (
            f"30 get() calls must sleep >=58s in total (<=30 req/60s ceiling). "
            f"Got: {total_slept:.1f}s. "
            f"Ensure AWClient sleeps >=2s per call (30 * 2.0 = 60.0s; 58.0s is the floor "
            f"allowing for minor float drift)."
        )


# ---------------------------------------------------------------------------
# User-Agent identification
# ---------------------------------------------------------------------------


class TestUserAgent:
    def test_session_identifies_wahl_chat(self) -> None:
        """The retrying session must carry a wahl.chat-identifying User-Agent
        (AW fair-use policy asks API consumers to identify themselves)."""
        c = AWClient()
        session = c._get_session()
        assert session.headers.get("User-Agent") == (
            "wahl.chat-ingestion/2.0 (https://wahl.chat)"
        )
