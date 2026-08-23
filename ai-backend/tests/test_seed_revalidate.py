# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Frontend cache bust: optional after seed, required on the standalone script."""

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


def _patch_urlopen(seed, monkeypatch, fn):
    monkeypatch.setattr(seed.frontend_cache.urllib.request, "urlopen", fn)


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

    _patch_urlopen(seed, monkeypatch, _fail)
    seed.revalidate_frontend_cache(["abgeordnetenhauswahl-berlin-2026"])


def test_cloud_seed_without_secret_warns_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(monkeypatch, ENV="prod")
    monkeypatch.delenv("REVALIDATE_SECRET", raising=False)
    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.delenv("REVALIDATE_URL", raising=False)

    def _fail(*_a: object, **_k: object) -> None:
        raise AssertionError("missing secret must not call /api/revalidate")

    _patch_urlopen(seed, monkeypatch, _fail)
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

    _patch_urlopen(seed, monkeypatch, _urlopen)
    seed.revalidate_frontend_cache(["abgeordnetenhauswahl-berlin-2026"])

    assert captured["url"] == "https://wahl.chat/api/revalidate"
    assert captured["timeout"] == 30
    headers = {k.lower(): v for k, v in captured["headers"].items()}  # type: ignore[union-attr]
    assert headers["authorization"] == "Bearer test-secret"
    body = captured["body"]
    assert body["tags"] == list(seed.frontend_cache.SEED_CACHE_TAGS)
    assert body["paths"] == [
        "/",
        "/abgeordnetenhauswahl-berlin-2026",
        "/abgeordnetenhauswahl-berlin-2026/sources",
    ]


def test_dev_env_defaults_to_dev_wahl_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="dev",
        REVALIDATE_SECRET="test-secret",
    )
    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.delenv("REVALIDATE_URL", raising=False)
    captured: dict[str, str] = {}

    def _urlopen(request: object, timeout: int = 0) -> _FakeResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        return _FakeResponse()

    _patch_urlopen(seed, monkeypatch, _urlopen)
    seed.revalidate_frontend_cache([])
    assert captured["url"] == "https://dev.wahl.chat/api/revalidate"


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

    _patch_urlopen(seed, monkeypatch, _urlopen)
    seed.revalidate_frontend_cache([])
    assert captured["url"] == "https://preview.example/api/revalidate"


def test_http_error_does_not_fail_the_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    _patch_urlopen(seed, monkeypatch, _urlopen)
    seed.revalidate_frontend_cache(["bundestagswahl-2025"])


def test_standalone_script_requires_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(monkeypatch, ENV="prod")
    monkeypatch.delenv("REVALIDATE_SECRET", raising=False)
    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.delenv("REVALIDATE_URL", raising=False)
    assert seed.frontend_cache.main(["--context", "bundestagswahl-2025"]) == 1


def test_standalone_script_posts_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="prod",
        REVALIDATE_SECRET="test-secret",
    )
    captured: dict[str, object] = {}

    def _urlopen(request: object, timeout: int = 0) -> _FakeResponse:
        captured["body"] = json.loads(request.data.decode())  # type: ignore[attr-defined]
        return _FakeResponse()

    _patch_urlopen(seed, monkeypatch, _urlopen)
    assert (
        seed.frontend_cache.main(["--context", "abgeordnetenhauswahl-berlin-2026"]) == 0
    )
    body = captured["body"]
    assert body["paths"] == [
        "/",
        "/abgeordnetenhauswahl-berlin-2026",
        "/abgeordnetenhauswahl-berlin-2026/sources",
    ]


def test_standalone_script_exits_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        ENV="prod",
        REVALIDATE_SECRET="test-secret",
    )

    def _urlopen(*_a: object, **_k: object) -> None:
        raise URLError("timed out")

    _patch_urlopen(seed, monkeypatch, _urlopen)
    assert seed.frontend_cache.main(["--context", "bundestagswahl-2025"]) == 1
