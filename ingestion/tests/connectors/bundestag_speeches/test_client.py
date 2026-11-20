# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from types import SimpleNamespace
from typing import Any

import pytest

from ingestion.connectors.bundestag_speeches import client
from ingestion.connectors.bundestag_speeches.client import (
    DipChallengeError,
    TooLargeError,
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


class _Streamed:
    """A streamed response; ``read`` records how many pieces were taken."""

    def __init__(self, pieces: list[bytes], length: str | None = None) -> None:
        self.url = PDF
        self.headers = {} if length is None else {"Content-Length": length}
        self.pieces = pieces
        self.read = 0

    def __enter__(self) -> "_Streamed":
        return self

    def __exit__(self, *exc: Any) -> None:
        pass

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int) -> Any:
        for piece in self.pieces:
            self.read += 1
            yield piece


def _serve(monkeypatch: pytest.MonkeyPatch, response: _Streamed) -> None:
    monkeypatch.setattr(client.requests, "get", lambda url, timeout, stream: response)


def test_a_pdf_within_the_limit_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, _Streamed([b"%PDF", b"-1.7"], length="8"))
    assert fetch_bytes(PDF, max_bytes=8) == b"%PDF-1.7"


def test_a_declared_size_over_the_limit_is_not_downloaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _Streamed([b"%PDF-1.7"], length="284803072")
    _serve(monkeypatch, response)
    with pytest.raises(TooLargeError):
        fetch_bytes(PDF, max_bytes=50)
    assert response.read == 0


def test_an_undeclared_size_stops_once_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _Streamed([b"x" * 40, b"x" * 40, b"x" * 40])
    _serve(monkeypatch, response)
    with pytest.raises(TooLargeError):
        fetch_bytes(PDF, max_bytes=50)
    assert response.read == 2


def test_curl_is_given_the_limit_too(monkeypatch: pytest.MonkeyPatch) -> None:
    challenge = _Streamed([])
    challenge.url = "https://dserver.bundestag.de/.enodia/challenge"
    _serve(monkeypatch, challenge)
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> Any:
        commands.append(command)
        return SimpleNamespace(returncode=63, stdout=b"", stderr=b"")

    monkeypatch.setattr(client.subprocess, "run", run)
    with pytest.raises(TooLargeError):
        fetch_bytes(PDF, max_bytes=50)
    assert commands[0][-3:] == ["--max-filesize", "50", PDF]
