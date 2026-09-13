# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
AWClient — the single I/O home for all Abgeordnetenwatch v2 API calls.

Design goals:
  - All outbound HTTP to AW routes through this module.  No other module calls
    requests.get() against the AW host.
  - Fixed >=2s inter-request delay enforces the <=30 req/min fair-use ceiling
    (simple fixed-spacing pacing).
  - Retrying session with exponential backoff on 429/5xx.
  - Row-count pagination in get_all(): range_end is the NUMBER of rows to
    return; range_start advances by the rows actually delivered (verified
    against the live API).
  - meta.status guard: any response with meta.status != 'ok' raises ValueError
    so callers never silently process bad data.

Security notes:
  SSRF mitigation: ``_AW_BASE`` is a module-level constant string
  literal.  ``get()`` and ``get_all()`` accept only a ``path`` segment, never
  a full URL or host.  The host cannot be overridden by a caller argument.

  Denial of Service (unbounded pagination): ``get_all`` stops when
  ``start >= meta.result.total``; ``get_votes_for_poll`` uses a single call
  with range_end=800 (verified: 19th Bundestag polls have <=750 votes each).

  Denial of Service (AW 429 cascade): Fixed >=2s spacing keeps us
  at <=30 req/min.  ``Retry(respect_retry_after_header=True)`` backs off on
  429 responses from the server side.

  Tampering (malformed JSON): ``raise_for_status()`` on HTTP errors;
  meta.status guard raises on API error envelope; timeout=30 bounds hangs.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (SSRF guard — pinned module-level constant, never derived
# from a method argument or user input)
# ---------------------------------------------------------------------------

# The AW v2 base URL is a pinned constant.  It is NEVER constructed from a
# method argument.  callers supply only the path segment after this base.
_AW_BASE = "https://www.abgeordnetenwatch.de/api/v2"

# Fixed inter-request delay enforcing <=30 req/60s fair-use ceiling.
# Overridable via env var for testing/calibration; production default is 2.0s.
_AW_REQUEST_DELAY_S = float(os.getenv("AW_REQUEST_DELAY_S", "2.0"))

# Retry configuration.
_MAX_RETRIES = 5

# User-Agent identifying wahl.chat to the AW API (fair-use policy asks
# consumers to identify themselves so they can be contacted about usage).
_USER_AGENT = "wahl.chat-ingestion/2.0 (https://wahl.chat)"

# Rows requested per page in get_all() — range_end is a row COUNT, so every
# page asks for exactly this many rows (see get_all's pagination notes).
_PAGE_SIZE = 100

# Hard page cap for get_all().  meta.result.total is server-controlled;
# a malicious or buggy AW response advertising a huge total would otherwise drive
# millions of 2s-paced requests (effectively an infinite loop).  At _PAGE_SIZE=100
# this caps a single get_all() at 10_000 items, which is far above any real AW
# legislature poll/fraction count — exceeding it signals a bad response.
_MAX_PAGES = 100

# Single-call vote fetch window.  Verified: 19th Bundestag polls
# have at most ~750 votes each (poll 3602 = 709, poll 4539 = 736, poll 5957 = 733).
# get_votes_for_poll RAISES if meta.result.total exceeds this so other
# legislatures with larger fractions cannot silently truncate the vote list.
_VOTES_RANGE_END = 800


# ---------------------------------------------------------------------------
# AWClient
# ---------------------------------------------------------------------------


class AWClient:
    """Paced, retrying HTTP client for the Abgeordnetenwatch v2 JSON API.

    All AW API calls route through this class.  It enforces:
    - Fixed >=2s inter-request sleep before each call (<=30 req/min)
    - Retrying session with backoff on 429/5xx
    - meta.status guard — raises ValueError on API error envelopes
    - Row-count pagination in get_all() (range_end = rows per page)
    - Pinned base URL (SSRF guard)

    Usage::

        client = AWClient()
        poll = client.get("polls/3602")
        polls = client.get_all("polls", {"field_legislature": 111})
        votes = client.get_votes_for_poll(3602)
    """

    def __init__(self) -> None:
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """Build the retrying session lazily on first use.

        Importing this module is side-effect-free; the session is not created
        until the first live get() call.

        Retry policy:
          - Retry(total=5) — up to 5 retries on top of the original request,
            i.e. up to 6 attempts in total
          - backoff_factor=1.0 — urllib3 2.x sleeps 1s, 2s, 4s, 8s, 16s before
            the successive retries
          - status_forcelist=(429, 500, 502, 503, 504)
          - respect_retry_after_header=True — honours server-side 429 Retry-After
          - allowed_methods={"GET"} — only idempotent GETs are retried

        The session identifies wahl.chat via a User-Agent header (AW fair-use
        policy asks API consumers to identify themselves).
        """
        if self._session is None:
            retry = Retry(
                total=_MAX_RETRIES,
                backoff_factor=1.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET"}),
                respect_retry_after_header=True,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session = requests.Session()
            session.mount("https://", adapter)
            session.headers.update({"User-Agent": _USER_AGENT})
            self._session = session
        return self._session

    def get(self, path: str, params: dict | None = None) -> dict:
        """Make a single paced GET request to the AW v2 API.

        The inter-request sleep happens BEFORE the HTTP call so that even the
        first call in a batch is counted against the ceiling.

        Args:
            path: Path segment after _AW_BASE (e.g., ``"polls/3602"`` or
                  ``"polls"``).  Must NOT include a host or scheme — the host
                  is always _AW_BASE.
            params: Optional query parameters dict (e.g., ``{"field_legislature": 111}``).

        Returns:
            The full parsed JSON response dict (including meta and data).

        Raises:
            requests.HTTPError: On non-200 HTTP responses (via raise_for_status).
            ValueError: When meta.status != "ok" — the API returned an error
                        envelope.
            requests.exceptions.Timeout: When the request exceeds 30s.
        """
        # Sleep before every request — even the first call in a batch.
        # This ensures 30 sequential calls take >=60s (>=58s after float rounding).
        time.sleep(_AW_REQUEST_DELAY_S)

        url = f"{_AW_BASE}/{path}"
        response = self._get_session().get(url, params=params, timeout=30)
        response.raise_for_status()

        d: dict = response.json()

        # meta.status guard — raises instead of returning bad data.
        # A meta.status != "ok" response (e.g., invalid parameter name)
        # still returns HTTP 200; we must check the envelope explicitly.
        if d.get("meta", {}).get("status") != "ok":
            status_message = d.get("meta", {}).get("status_message", "unknown error")
            raise ValueError(f"AW API error: {status_message}")

        return d

    def get_all(self, path: str, params: dict | None = None) -> list:
        """Paginate through all results, advancing by the delivered row count.

        AW's ``range_end`` is the NUMBER of rows to return, not an absolute end
        index: ``range_start=100&range_end=200`` returns 200 rows from position
        100. Each page therefore requests a fixed window of ``_PAGE_SIZE`` rows
        (``range_end=_PAGE_SIZE``) and advances ``range_start`` by the number of
        rows actually delivered, until ``range_start >= meta.result.total``.
        (Requesting ``range_end=start+_PAGE_SIZE`` would grow the window every
        page and re-fetch already-collected rows.)
        A hard page cap (_MAX_PAGES) bounds the loop even if the
        server-controlled ``total`` is absurdly large, and the envelope is read
        with guarded ``.get()`` so a 200-OK response missing ``result``/``data``
        raises the ValueError contract instead of a bare KeyError.

        Args:
            path: Path segment after _AW_BASE (e.g., ``"polls"``).
            params: Base query parameters (e.g., ``{"field_legislature": 111}``).
                    range_start and range_end are managed internally and will
                    override any values passed here.

        Returns:
            Concatenated ``data`` lists from all pages.

        Raises:
            ValueError: When a page envelope is missing ``meta.result.total`` or
                        a list ``data``.
        """
        # Work from a copy so we don't mutate the caller's dict
        page_params: dict = dict(params or {})
        start = 0
        all_data: list = []
        total: int | None = None
        pages = 0

        while total is None or start < total:
            # Hard page cap — never loop more than _MAX_PAGES times even if
            # the server advertises an absurd total.
            if pages >= _MAX_PAGES:
                logger.warning(
                    "get_all: page cap _MAX_PAGES=%s hit for path=%r "
                    "(total advertised=%s, fetched=%s) — stopping pagination early.",
                    _MAX_PAGES,
                    path,
                    total,
                    len(all_data),
                )
                break

            page_params["range_start"] = start
            # range_end is a ROW COUNT (not an absolute end index): request a
            # fixed page of _PAGE_SIZE rows. Using start+_PAGE_SIZE here would
            # request an ever-larger window and re-fetch already-collected rows.
            page_params["range_end"] = _PAGE_SIZE

            resp = self.get(path, page_params)

            # Guarded envelope access — a 200-OK envelope missing
            # result/data raises the ValueError contract, not a bare KeyError.
            meta_result = resp.get("meta", {}).get("result")
            if not isinstance(meta_result, dict) or "total" not in meta_result:
                raise ValueError(
                    f"AW API response for path={path!r} missing meta.result.total"
                )
            total = meta_result["total"]

            data = resp.get("data")
            if not isinstance(data, list):
                raise ValueError(
                    f"AW API response for path={path!r} missing or non-list 'data'"
                )

            all_data.extend(data)
            pages += 1

            # Advance by the rows ACTUALLY delivered — correct for a full page,
            # the short final tail, or a server cap below _PAGE_SIZE, and it
            # never skips or overlaps. A page returning nothing while more rows
            # are advertised would loop forever, so stop (results may be short).
            if not data:
                if total is not None and start < total:
                    logger.warning(
                        "get_all: path=%r returned 0 rows at range_start=%s "
                        "(total advertised=%s) — stopping; results may be incomplete.",
                        path,
                        start,
                        total,
                    )
                break
            start += len(data)

        return all_data

    def get_votes_for_poll(self, poll_id: int) -> list:
        """Fetch all per-mandate votes for a single poll in one API call.

        The AW votes endpoint returns ~700-750 votes per Bundestag legislature
        poll.  Using range_end=800 fetches all of them in a single request
        without pagination, minimising the number of API calls.

        Verified: 19th Bundestag polls have at most ~750 votes (poll 3602 = 709,
        poll 4539 = 736, poll 5957 = 733) — well within range_end=800.

        The connector is parameterized by AW_LEGISLATURE_ID and is meant
        to serve other legislatures.  If a poll reports more than _VOTES_RANGE_END
        total votes, the single-call fetch would silently truncate the vote list
        and produce wrong tallies/stances.  We read ``meta.result.total`` and
        RAISE loudly rather than truncate — a multi-legislature correctness guard.

        Args:
            poll_id: AW integer poll ID (e.g., 3602).

        Returns:
            The ``data`` list from the votes endpoint response — a list of
            per-mandate vote dicts each with ``vote``, ``fraction``, ``mandate``,
            and ``poll`` fields.

        Raises:
            ValueError: When the votes endpoint reports more total votes than
                        _VOTES_RANGE_END (would silently truncate).
        """
        resp = self.get(
            "votes",
            params={"poll": poll_id, "range_start": 0, "range_end": _VOTES_RANGE_END},
        )

        # A missing/non-int total must itself raise — otherwise the overflow guard below
        # is silently bypassed and a truncated list could pass through as complete.
        total = resp.get("meta", {}).get("result", {}).get("total")
        if not isinstance(total, int):
            raise ValueError(
                f"AW votes response for poll {poll_id} has missing/non-int "
                f"meta.result.total={total!r}; cannot verify the vote list is complete."
            )

        # Detect overflow — raise instead of silently truncating.
        if total > _VOTES_RANGE_END:
            raise ValueError(
                f"AW poll {poll_id} reports {total} votes, exceeding the "
                f"single-call window _VOTES_RANGE_END={_VOTES_RANGE_END}. "
                "Single-call fetch would silently truncate the vote list and "
                "corrupt tallies. Paginate via get_all or raise the window."
            )

        data = resp.get("data")
        if not isinstance(data, list):
            raise ValueError(
                f"AW votes response for poll {poll_id} missing or non-list 'data'"
            )
        # Detect UNDER-delivery — the endpoint may cap items per response even below
        # range_end. If fewer than `total` votes came back, tallies would be computed
        # from a truncated list. Raise rather than silently under-count.
        if len(data) != total:
            raise ValueError(
                f"AW votes for poll {poll_id}: expected {total} votes but received "
                f"{len(data)} in a single call (server-side page cap?). Tallies would be "
                "wrong — paginate via get_all instead of a single-call fetch."
            )
        return data
