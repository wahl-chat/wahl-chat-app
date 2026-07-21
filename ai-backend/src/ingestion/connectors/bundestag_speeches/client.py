# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""DipClient — the single I/O home for all DIP Bundestag API calls.

Design goals (mirrors abgeordnetenwatch/client.py posture):
  - BASE_URL is a pinned module constant — host never derived from a caller arg.
  - curl_get uses a fixed arg list, no shell=True.
  - DipClient.get paces requests with a 0.2 s sleep (DIP cap = 25 concurrent).
  - Enodia challenge-page redirect handled via curl fallback.

Public API:
  DipClient(api_key, sleep=0.2)  — paced session; .get(endpoint, params) and .pages(endpoint, params)
  fetch_text(url) -> str          — fetch XML text, curl fallback on challenge redirect
  curl_get(url, accept) -> str    — fixed-arg subprocess curl, no shell=True
"""

from __future__ import annotations

import json
import subprocess
import time
from urllib.parse import urlencode

import requests

import logging as _logging

from .constants import BASE_URL, _MAX_PAGES

_client_logger = _logging.getLogger(__name__)


class DipChallengeError(RuntimeError):
    """Raised when the Bundestag .enodia/challenge page cannot be bypassed."""


class DipClient:
    """Paced HTTP client for the DIP Bundestag API v1.

    Enforces:
      - Sequential 0.2 s sleep between requests (DIP documented cap = 25 concurrent).
      - Up to 3 attempts per request; curl fallback on .enodia/challenge redirect.

    Args:
        api_key: DIP API key (from DIP_API_KEY env var — see connector._require_dip_key()).
        sleep: Inter-request delay in seconds (default 0.2).
    """

    def __init__(self, api_key: str, sleep: float = 0.2) -> None:
        self.api_key = api_key
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 bundestag-speeches-student-project/1.0",
            }
        )

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a single GET request to the DIP API, with challenge-page fallback.

        Args:
            endpoint: API path (e.g. "/plenarprotokoll").
            params: Query parameters (apikey is injected automatically).

        Returns:
            Parsed JSON response dict.

        Raises:
            requests.HTTPError: on non-2xx responses (after all attempts).
            DipChallengeError: if curl fallback also hits the challenge page.
        """
        params = dict(params or {})
        params["apikey"] = self.api_key
        params["format"] = "json"
        url = BASE_URL + endpoint + "?" + urlencode(params, doseq=True)

        for attempt in range(3):
            response = self.session.get(BASE_URL + endpoint, params=params, timeout=60)
            if ".enodia/challenge" not in response.url:
                break
            if attempt == 2:
                data = curl_get(url, accept="application/json")
                time.sleep(self.sleep)
                return json.loads(data)
            time.sleep(5 * (attempt + 1))

        response.raise_for_status()
        time.sleep(self.sleep)
        return response.json()

    def pages(self, endpoint: str, params: dict | None = None):  # type: ignore[return]
        """Walk all cursor-pages for an endpoint, yielding one page dict at a time.

        Stops when the cursor is absent or unchanged (DIP documented cursor-until-unchanged
        contract). Each page dict contains a "documents" list and a "cursor" string.

        Args:
            endpoint: API path (e.g. "/plenarprotokoll").
            params: Base query parameters (cursor is injected automatically).

        Yields:
            dict: One page of API results.
        """
        params = dict(params or {})
        last_cursor = None
        page_count = 0

        while True:
            # Enforce a hard page cap (mirrors the AW client's _MAX_PAGES) so a
            # stuck/malformed cursor cannot loop indefinitely.  _MAX_PAGES (from
            # constants.py) is generous enough for any full legislature's protocol
            # list but provably finite.
            page_count += 1
            if page_count > _MAX_PAGES:
                _client_logger.warning(
                    "DipClient.pages(): hit hard page cap of %d for endpoint %r — stopping.",
                    _MAX_PAGES,
                    endpoint,
                )
                break

            data = self.get(endpoint, params)
            yield data

            cursor = data.get("cursor")
            if not cursor or cursor == last_cursor:
                break

            params["cursor"] = cursor
            last_cursor = cursor


def fetch_text(url: str) -> str:
    """Fetch text content from a URL, using curl fallback on .enodia/challenge redirect.

    Used to retrieve protocol XML from DIP fundstelle.xml_url.

    Args:
        url: Full URL to fetch (DIP-returned xml_url — not user-supplied).

    Returns:
        Response text (UTF-8 decoded).

    Raises:
        requests.HTTPError: on non-2xx responses.
        DipChallengeError: if curl fallback fails.
    """
    response = requests.get(url, timeout=60)
    if ".enodia/challenge" in response.url:
        return curl_get(url, accept="text/xml")

    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def curl_get(url: str, accept: str = "*/*") -> str:
    """Fetch a URL via subprocess curl with a fixed argument list (no shell=True).

    Security: the URL is DIP-derived, not user-supplied; the arg
    list is fixed at call time and never passed through a shell.

    Args:
        url: URL to fetch (DIP-derived; not user-supplied).
        accept: Accept header value (default "*/*").

    Returns:
        Response body as a string.

    Raises:
        DipChallengeError: if curl exits non-zero.
    """
    # Fixed arg list — no shell=True
    command = ["curl", "-sS", "-L", "--fail", "-H", f"Accept: {accept}", url]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if result.returncode != 0:
        raise DipChallengeError(
            result.stderr.strip() or "curl could not fetch the official Bundestag URL"
        )
    return result.stdout
