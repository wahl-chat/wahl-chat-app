# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""OpTvClient._get_json fallback tests.

Focus: on a persistent non-2xx the curl fallback error must carry the original
HTTP status context (e.g. 404) so bulk-backfill failures are triageable. No
network / no real curl — the requests.Session and curl_get are stubbed.
"""

from __future__ import annotations

import pytest

client_mod = pytest.importorskip(
    "src.ingestion.connectors.openparliament_tv.client",
    reason="op client not yet implemented",
)


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def json(self) -> dict:  # pragma: no cover - not reached on non-200
        return {}


class _FakeSession:
    """Always returns the same non-2xx response (drives the curl fallback)."""

    def __init__(self, status_code: int) -> None:
        self._status_code = status_code
        self.headers = {}

    def get(self, url: str, timeout: int = 60) -> _FakeResponse:
        return _FakeResponse(self._status_code)


def test_get_json_fallback_includes_http_status(monkeypatch) -> None:
    """a 404 loop whose curl fallback also fails surfaces HTTP 404 in the error."""
    op = client_mod.OpTvClient(sleep=0)
    op.session = _FakeSession(404)

    # curl fallback also fails → raises OpTvChallengeError with only stderr.
    def _boom(url: str, accept: str = "*/*") -> str:
        raise client_mod.OpTvChallengeError("curl: (22) The requested URL returned error")

    monkeypatch.setattr(client_mod, "curl_get", _boom)
    monkeypatch.setattr(client_mod.time, "sleep", lambda *_: None)

    with pytest.raises(client_mod.OpTvChallengeError) as excinfo:
        op._get_json("https://raw.githubusercontent.com/x/y/processed/20101-session.json")

    msg = str(excinfo.value)
    assert "404" in msg, f"fallback error must carry the HTTP status; got {msg!r}"
    assert "curl fallback also failed" in msg


def test_get_json_fallback_succeeds_when_curl_recovers(monkeypatch) -> None:
    """A non-2xx whose curl fallback SUCCEEDS still returns parsed JSON (no regression)."""
    op = client_mod.OpTvClient(sleep=0)
    op.session = _FakeSession(503)

    monkeypatch.setattr(client_mod, "curl_get", lambda url, accept="*/*": '{"ok": true}')
    monkeypatch.setattr(client_mod.time, "sleep", lambda *_: None)

    assert op._get_json("https://raw.githubusercontent.com/x/y/processed/20101-session.json") == {
        "ok": True
    }
