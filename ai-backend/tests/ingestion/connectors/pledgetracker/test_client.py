# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
PledgeQueueClient unit tests (no network; the requests module is faked).

Tests defined here:
  - test_base_url_constant_pinned: the default queue endpoint never drifts (SSRF guard).
  - test_submit_then_poll_until_done: submit → queued → running → done returns the
    result payload, and every request carries the X-Api-Key header.
  - test_failed_job_raises_with_api_error: a failed job surfaces the API's error text.
  - test_timeout_raises: no terminal state within timeout_s → PledgeJobTimeoutError.
  - test_auth_error_fails_fast: 401 raises immediately (no retry loop).
  - test_missing_api_key_rejected_at_construction: client refuses to build without a key.
"""

from __future__ import annotations

import json

import pytest

import src.ingestion.connectors.pledgetracker.client as client_module
from src.ingestion.connectors.pledgetracker.client import (
    DEFAULT_BASE_URL,
    PledgeJobFailedError,
    PledgeJobTimeoutError,
    PledgeQueueClient,
    PledgeQueueError,
)

_RESULT = {"status": "success", "language": "de", "events": []}


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text or json.dumps(payload)
        self.ok = status_code < 400

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise client_module.requests.HTTPError(f"HTTP {self.status_code}")


class _FakeRequests:
    """Stands in for the ``requests`` module inside client.py."""

    HTTPError = Exception
    RequestException = Exception

    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)

    def get(self, url: str, **kwargs) -> _FakeResponse:
        return self.request("GET", url, **kwargs)


def _make_client(
    monkeypatch: pytest.MonkeyPatch, responses: list[_FakeResponse]
) -> tuple[PledgeQueueClient, _FakeRequests]:
    fake = _FakeRequests(responses)
    monkeypatch.setattr(client_module, "requests", fake)
    client = PledgeQueueClient(
        base_url="https://queue.test", api_key="test-key", sleep=lambda _s: None
    )
    return client, fake


def test_base_url_constant_pinned() -> None:
    """The default queue endpoint never drifts (SSRF guard)."""
    assert DEFAULT_BASE_URL == "https://pledgequeue.ramialy.com"


def test_submit_then_poll_until_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """Submit → queued → running → done returns the result; X-Api-Key on every call."""
    client, fake = _make_client(
        monkeypatch,
        [
            _FakeResponse({"id": 42, "status": "queued", "position": 1}),
            _FakeResponse({"id": 42, "status": "queued", "position": 1}),
            _FakeResponse(
                {"id": 42, "status": "running", "position": 0, "running_for_s": 95}
            ),
            _FakeResponse({"id": 42, "status": "done", "result": _RESULT}),
        ],
    )

    job_id = client.submit_job(
        {"claim": "x", "pledge_date": "2021-03-27", "pledge_author": "CDU"}
    )
    assert job_id == 42

    result = client.wait_for_job(job_id, timeout_s=600)
    assert result["status"] == "success"

    assert all(call["headers"] == {"X-Api-Key": "test-key"} for call in fake.calls)
    assert fake.calls[0]["method"] == "POST"
    assert fake.calls[0]["json"] == {
        "inputs": {"claim": "x", "pledge_date": "2021-03-27", "pledge_author": "CDU"}
    }


def test_failed_job_raises_with_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed job surfaces the pipeline's error text."""
    client, _ = _make_client(
        monkeypatch,
        [_FakeResponse({"id": 7, "status": "failed", "error": "pipeline exploded"})],
    )
    with pytest.raises(PledgeJobFailedError, match="pipeline exploded"):
        client.wait_for_job(7, timeout_s=600)


def test_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """No terminal state within timeout_s raises PledgeJobTimeoutError."""
    client, _ = _make_client(
        monkeypatch,
        [_FakeResponse({"id": 7, "status": "queued", "position": 3})],
    )
    with pytest.raises(PledgeJobTimeoutError):
        client.wait_for_job(7, timeout_s=0)


def test_auth_error_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 is permanent — raise immediately with the API message, no retries."""
    client, fake = _make_client(
        monkeypatch,
        [_FakeResponse({}, status_code=401, text="missing or wrong X-Api-Key")],
    )
    with pytest.raises(PledgeQueueError, match="401"):
        client.submit_job({"claim": "x"})
    assert len(fake.calls) == 1


def test_missing_api_key_rejected_at_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The client refuses to construct without PLEDGETRACKER_API_KEY."""
    monkeypatch.delenv("PLEDGETRACKER_API_KEY", raising=False)
    with pytest.raises(PledgeQueueError, match="PLEDGETRACKER_API_KEY"):
        PledgeQueueClient(base_url="https://queue.test")
