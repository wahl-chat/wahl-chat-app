# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from types import SimpleNamespace
from typing import Any

import pytest

from ingestion.connectors.bundestag_speeches import client
from ingestion.connectors.bundestag_speeches.client import (
    DipChallengeError,
    fetch_bytes,
)

PDF = "https://dserver.bundestag.de/btp/21/21045.pdf"


def _response(url: str, content: bytes = b"") -> Any:
    return SimpleNamespace(url=url, content=content, raise_for_status=lambda: None)


def test_a_pdf_is_returned_as_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client.requests, "get", lambda url, timeout: _response(url, b"%PDF-1.7")
    )
    assert fetch_bytes(PDF) == b"%PDF-1.7"


def test_a_challenge_redirect_falls_back_to_curl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The challenge page answers 200 with HTML; read as a PDF it would fail.
    monkeypatch.setattr(
        client.requests,
        "get",
        lambda url, timeout: _response(
            "https://dserver.bundestag.de/.enodia/challenge"
        ),
    )
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> Any:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=b"%PDF-1.7", stderr=b"")

    monkeypatch.setattr(client.subprocess, "run", run)
    assert fetch_bytes(PDF) == b"%PDF-1.7"
    assert commands[0][-1] == PDF


def test_a_failed_curl_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client.requests,
        "get",
        lambda url, timeout: _response(
            "https://dserver.bundestag.de/.enodia/challenge"
        ),
    )
    monkeypatch.setattr(
        client.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            returncode=22, stdout=b"", stderr=b"curl: (22) 403"
        ),
    )
    with pytest.raises(DipChallengeError, match="403"):
        fetch_bytes(PDF)
