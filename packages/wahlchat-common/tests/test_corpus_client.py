# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from __future__ import annotations

from typing import Any

import pytest

from wahlchat_common import corpus


class _FakeClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_the_default_client_waits_long_enough_to_build_an_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(corpus, "QdrantClient", _FakeClient)
    monkeypatch.delenv("QDRANT_TIMEOUT", raising=False)
    client: Any = corpus._make_client()
    assert client.kwargs["timeout"] == 120


def test_qdrant_timeout_overrides_the_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(corpus, "QdrantClient", _FakeClient)
    monkeypatch.setenv("QDRANT_TIMEOUT", "600")
    client: Any = corpus._make_client()
    assert client.kwargs["timeout"] == 600
