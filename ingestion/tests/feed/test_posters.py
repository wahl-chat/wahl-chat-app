# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import subprocess
from typing import Any, Optional

import pytest

from ingestion.feed import posters

VIDEO = "https://video/s1.mp4"


class _Blob:
    def __init__(self, name: str, exists: bool) -> None:
        self.name = name
        self._exists = exists
        self.cache_control: Optional[str] = None
        self.uploads: list[tuple[bytes, dict[str, Any]]] = []

    def exists(self) -> bool:
        return self._exists

    def upload_from_string(self, data: bytes, **kwargs: Any) -> None:
        self.uploads.append((data, kwargs))


class _Bucket:
    def __init__(self, exists: bool = False) -> None:
        self.exists = exists
        self.blobs: list[_Blob] = []

    def blob(self, name: str) -> _Blob:
        self.blobs.append(_Blob(name, self.exists))
        return self.blobs[-1]


def test_the_poster_path_is_stable_and_moves_with_the_start() -> None:
    path = posters.poster_path(VIDEO, 3.0)
    assert path == posters.poster_path(VIDEO, 3.0)
    assert path.startswith("public/feed/posters/") and path.endswith(".webp")
    assert path != posters.poster_path(VIDEO, 3.5)
    assert path != posters.poster_path("https://video/s2.mp4", 3.0)


def test_ffmpeg_seeks_before_opening_the_input() -> None:
    # An input seek lands on the frame a browser shows for ``#t=``.
    command = posters.ffmpeg_command(VIDEO, 7.3)
    assert command[command.index("-ss") + 1] == "7.3"
    assert command.index("-ss") < command.index("-i")
    assert command[command.index("-i") + 1] == VIDEO
    assert command[command.index("-c:v") + 1] == "libwebp"
    assert command[-1] == "pipe:1"


def test_cut_poster_returns_the_frame_ffmpeg_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        seen.append(command)
        assert kwargs["check"] is True and kwargs["timeout"]
        return subprocess.CompletedProcess(command, 0, stdout=b"webp", stderr=b"")

    monkeypatch.setattr(posters.subprocess, "run", run)
    assert posters.cut_poster(VIDEO, 3.0) == b"webp"
    assert seen == [posters.ffmpeg_command(VIDEO, 3.0)]


def test_a_new_poster_is_cut_and_uploaded_public_and_immutable() -> None:
    bucket = _Bucket(exists=False)
    cuts: list[tuple[str, float]] = []

    def cut(video_url: str, start: float) -> bytes:
        cuts.append((video_url, start))
        return b"webp"

    make = posters.poster_maker("dev", bucket=bucket, cut=cut)
    assert make is not None
    url = make(VIDEO, 3.0)
    path = posters.poster_path(VIDEO, 3.0)
    assert (
        url
        == f"https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app/{path}"
    )
    assert cuts == [(VIDEO, 3.0)]
    [blob] = bucket.blobs
    assert blob.name == path
    assert blob.cache_control == posters.POSTER_CACHE_CONTROL
    [(data, kwargs)] = blob.uploads
    assert data == b"webp"
    assert kwargs == {"content_type": "image/webp", "predefined_acl": "publicRead"}


def test_an_existing_poster_is_not_cut_again() -> None:
    bucket = _Bucket(exists=True)

    def cut(video_url: str, start: float) -> bytes:
        raise AssertionError("an uploaded poster is reused")

    make = posters.poster_maker("prod", bucket=bucket, cut=cut)
    assert make is not None
    url = make(VIDEO, 3.0)
    assert url is not None and "wahl-chat.firebasestorage.app" in url
    assert bucket.blobs[0].uploads == []


def test_a_failed_cut_gives_no_poster() -> None:
    def cut(video_url: str, start: float) -> bytes:
        raise subprocess.CalledProcessError(1, "ffmpeg")

    make = posters.poster_maker("dev", bucket=_Bucket(), cut=cut)
    assert make is not None
    assert make(VIDEO, 3.0) is None


def test_no_poster_maker_without_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(posters.shutil, "which", lambda name: None)
    assert posters.poster_maker("dev", bucket=_Bucket()) is None
