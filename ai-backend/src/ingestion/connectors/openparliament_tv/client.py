# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""OpTvClient — the single I/O home for keyless openparliament.tv GitHub-bulk calls.

Design goals (mirrors bundestag_speeches/client.DipClient posture):
  - RAW_BASE / TREES_URL are pinned module constants — the fetch host is never
    derived from a caller arg or a session-supplied URI.
  - `curl_get` uses a fixed arg list, never routed through a shell
    (command-injection mitigation).
  - Requests are paced with a small sleep to be a good GitHub citizen (keyless).
  - `fetch_session_json` builds its URL ONLY from `RAW_BASE + a validated basename`;
    it NEVER fetches videoFileURI/audioFileURI/sourcePage (SSRF mitigation).

Public API:
  OpTvClient(sleep=0.2)
    .list_session_files() -> list[str]      — enumerate `processed/*-session.json` basenames
    .fetch_session_json(name) -> dict       — fetch + json.loads one session file
  curl_get(url, accept) -> str              — fixed-arg subprocess curl, never shell-routed
"""

from __future__ import annotations

import json
import logging as _logging
import re
import subprocess
import time

import requests

from .constants import (
    _MAX_TREE_ENTRIES,
    RAW_BASE,
    SESSION_FILE_RE,
    TREES_URL,
)

_client_logger = _logging.getLogger(__name__)

# Compiled once; matches `processed/YYYYY-session.json` full paths from the trees API.
_SESSION_FILE_PATTERN = re.compile(SESSION_FILE_RE)

# A validated basename is exactly `YYYYY-session.json` (the trees `path` minus the
# `processed/` prefix). Enforced before building the pinned RAW_BASE fetch URL so a
# hostile trees response can never inject `../` or an absolute URL into the path.
_BASENAME_PATTERN = re.compile(r"^2[01]\d{3}-session\.json$")


class OpTvChallengeError(RuntimeError):
    """Raised when a pinned-host session file cannot be fetched (HTTP + curl both failed)."""


class OpTvClient:
    """Paced, keyless HTTP client for the openparliament.tv GitHub bulk repository.

    Enforces:
      - Sequential `sleep`-second delay between requests (keyless GitHub courtesy).
      - Up to 3 attempts per fetch; fixed-arg `curl` fallback on redirect / non-2xx.
      - Fetch host pinned to RAW_BASE / TREES_URL; basenames validated before use.

    Args:
        sleep: Inter-request delay in seconds (default 0.2).
    """

    def __init__(self, sleep: float = 0.2) -> None:
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 wahl-chat-op-connector-student-project/1.0",
            }
        )

    def list_session_files(self) -> list[str]:
        """Enumerate `processed/*-session.json` bulk files via the GitHub trees API.

        GET the keyless recursive trees listing, filter `tree[].path` entries by
        SESSION_FILE_RE, and return the sorted set of matching basenames
        (`YYYYY-session.json`, i.e. the path with the `processed/` prefix stripped).

        Returns:
            Sorted list of session-file basenames.

        Raises:
            requests.HTTPError: on a non-2xx trees response (after all attempts).
        """
        data = self._get_json(TREES_URL)

        tree = data.get("tree", [])
        if not isinstance(tree, list):
            _client_logger.warning(
                "OpTvClient.list_session_files(): trees response 'tree' is not a list — got %s.",
                type(tree).__name__,
            )
            return []

        names: set[str] = set()
        for index, entry in enumerate(tree):
            if index >= _MAX_TREE_ENTRIES:
                _client_logger.warning(
                    "OpTvClient.list_session_files(): hit hard trees cap of %d entries — stopping.",
                    _MAX_TREE_ENTRIES,
                )
                break
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str):
                continue
            match = _SESSION_FILE_PATTERN.match(path)
            if match:
                names.add(f"{match.group(1)}-session.json")

        return sorted(names)

    def fetch_session_json(self, name: str) -> dict:
        """Fetch one `processed/{name}` session file and parse its JSON body.

        The URL is built ONLY from the pinned RAW_BASE plus a validated basename —
        NEVER from a session-supplied videoFileURI/audioFileURI/sourcePage (SSRF).

        Args:
            name: Session-file basename (e.g. "20101-session.json").

        Returns:
            Parsed JSON dict (JSON:API `{"meta": ..., "data": [...]}` shape).

        Raises:
            ValueError: if `name` is not a validated `YYYYY-session.json` basename.
            OpTvChallengeError: if both the HTTP request and the curl fallback fail.
        """
        if not _BASENAME_PATTERN.match(name):
            raise ValueError(
                f"refusing to fetch un-validated op session basename: {name!r} "
                "(must match 'YYYYY-session.json')"
            )

        # Pinned host + validated basename only — no source-supplied URI ever reaches here.
        url = f"{RAW_BASE}/{name}"
        return self._get_json(url)

    def _get_json(self, url: str) -> dict:
        """GET `url` (a pinned-host URL) and return parsed JSON, with a curl fallback.

        Up to 3 attempts; on a redirect away from the requested host or a non-2xx
        status on the final attempt, fall back to a fixed-arg curl fetch.
        """
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=60)
            except requests.RequestException:
                if attempt == 2:
                    body = curl_get(url, accept="application/json")
                    time.sleep(self.sleep)
                    return json.loads(body)
                time.sleep(2 * (attempt + 1))
                continue

            if response.status_code == 200:
                time.sleep(self.sleep)
                return response.json()

            if attempt == 2:
                try:
                    body = curl_get(url, accept="application/json")
                except OpTvChallengeError as exc:
                    # Preserve the original HTTP status (e.g. 404 vs 500)
                    # that the plain curl fallback error would otherwise drop —
                    # makes bulk backfill failures triageable. The curl posture
                    # (pinned host, fixed arg list) is untouched.
                    raise OpTvChallengeError(
                        f"HTTP {response.status_code} for {url}; "
                        f"curl fallback also failed: {exc}"
                    ) from exc
                time.sleep(self.sleep)
                return json.loads(body)
            time.sleep(2 * (attempt + 1))

        # Unreachable — the loop either returns or raises on the final attempt.
        raise OpTvChallengeError(f"could not fetch pinned op URL: {url}")


def curl_get(url: str, accept: str = "*/*") -> str:
    """Fetch a URL via subprocess curl with a fixed argument list (never shell-routed).

    Security: the URL is pinned-host-derived (RAW_BASE / TREES_URL + validated
    basename), not user-supplied; the arg list is fixed at call time and never
    passed through a shell (command-injection mitigation).

    Args:
        url: URL to fetch (pinned-host-derived; not source input).
        accept: Accept header value (default "*/*").

    Returns:
        Response body as a string.

    Raises:
        OpTvChallengeError: if curl exits non-zero.
    """
    # Fixed arg list — passed directly to subprocess, never routed through a shell.
    command = ["curl", "-sS", "-L", "--fail", "-H", f"Accept: {accept}", url]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if result.returncode != 0:
        raise OpTvChallengeError(
            result.stderr.strip()
            or "curl could not fetch the pinned openparliament.tv URL"
        )
    return result.stdout
