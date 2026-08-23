# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Frontend cache bust that follows a real-project Firestore seed."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from tests.test_local_mode import _load_seed_module


class _FakeResponse:
    def __init__(self, body: str = '{"revalidated":{}}') -> None:
        self._body = body.encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_a: object) -> None:
        return None


def test_emulator_seed_skips_revalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        FIRESTORE_EMULATOR_HOST="localhost:8081",
        GOOGLE_CLOUD_PROJECT="demo-wahl-chat",
    )

    def _fail(*_a: object, **_k: object) -> None:
        raise AssertionError("emulator seed must not call /api/revalidate")

    monkeypatch.setattr(seed.urllib.request, "urlopen", _fail)
    seed.revalidate_frontend_cache(["abgeordnetenhauswahl-berlin-2026"])


def test_cloud_seed_without_secret_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(monkeypatch, ENV="prod")
    monkeypatch.delenv("REVALIDATE_SECRET", raising=False)
    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.delenv("REVALIDATE_URL", raising=False)
    with pytest.raises(SystemExit):
        seed.revalidate_frontend_cache(["abgeordnetenhauswahl-berlin-2026"])


def test_cloud_seed_posts_tags_and_context_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="prod",
        REVALIDATE_SECRET="test-secret",
    )
    captured: dict[str, object] = {}

    def _urlopen(request: object, timeout: int = 0) -> _FakeResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())  # type: ignore[attr-defined]
        captured["body"] = json.loads(request.data.decode())  # type: ignore[attr-defined]
        return _FakeResponse()

    monkeypatch.setattr(seed.urllib.request, "urlopen", _urlopen)
    seed.revalidate_frontend_cache(["abgeordnetenhauswahl-berlin-2026"])

    assert captured["url"] == "https://wahl.chat/api/revalidate"
    assert captured["timeout"] == 30
    headers = {k.lower(): v for k, v in captured["headers"].items()}  # type: ignore[union-attr]
    assert headers["authorization"] == "Bearer test-secret"
    body = captured["body"]
    assert body["tags"] == list(seed.SEED_CACHE_TAGS)
    assert body["paths"] == [
        "/",
        "/abgeordnetenhauswahl-berlin-2026",
        "/abgeordnetenhauswahl-berlin-2026/sources",
    ]


def test_site_url_override_wins_over_prod_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="prod",
        REVALIDATE_SECRET="test-secret",
        SITE_URL="https://preview.example",
    )
    captured: dict[str, str] = {}

    def _urlopen(request: object, timeout: int = 0) -> _FakeResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        return _FakeResponse()

    monkeypatch.setattr(seed.urllib.request, "urlopen", _urlopen)
    seed.revalidate_frontend_cache([])
    assert captured["url"] == "https://preview.example/api/revalidate"


def test_http_error_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="prod",
        REVALIDATE_SECRET="test-secret",
    )

    def _urlopen(*_a: object, **_k: object) -> None:
        raise HTTPError(
            "https://wahl.chat/api/revalidate",
            401,
            "Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b"Unauthorized"),
        )

    monkeypatch.setattr(seed.urllib.request, "urlopen", _urlopen)
    with pytest.raises(SystemExit):
        seed.revalidate_frontend_cache(["bundestagswahl-2025"])


def test_network_error_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="prod",
        REVALIDATE_SECRET="test-secret",
    )

    def _urlopen(*_a: object, **_k: object) -> None:
        raise URLError("timed out")

    monkeypatch.setattr(seed.urllib.request, "urlopen", _urlopen)
    with pytest.raises(SystemExit):
        seed.revalidate_frontend_cache(["bundestagswahl-2025"])
