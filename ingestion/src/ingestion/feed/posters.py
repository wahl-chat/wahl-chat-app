# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""A still image for each debate card, cut from its video at ``start``.

Without one, the page has to open every card's video file to draw a
thumbnail: the Bundestag files keep their index at the end and a keyframe
only every two seconds, so each card cost about 1.5 MB before anyone pressed
play. A WebP still costs about 20 KB, and the player loads nothing until play.

The still must be the frame playback starts on. ffmpeg's ``-ss`` before
``-i`` seeks to the exact frame when it re-encodes, the same frame a browser
shows for ``#t=``; after ``-i`` it would also be exact but read the file from
the start.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from ingestion.connectors.manifesto_uploads.bucket_listing import storage_client
from ingestion.connectors.manifesto_uploads.storage_paths import (
    bucket_for_env,
    storage_url,
)

if TYPE_CHECKING:
    from google.cloud.storage import Bucket

logger = logging.getLogger(__name__)

# Video URL and start second in, public poster URL out; None when it could
# not be made this run.
PosterMaker = Callable[[str, float], Optional[str]]

# Under ``public/``: the only prefix the Storage rules let anyone read.
POSTER_PREFIX = "public/feed/posters/"
# Wide enough for the widest card on a 2x screen.
POSTER_WIDTH = 960
# The path changes with the video and the start, so a stored poster never
# changes and may be cached for good.
POSTER_CACHE_CONTROL = "public, max-age=31536000, immutable"
_CUT_TIMEOUT_S = 30


def poster_path(video_url: str, start: float) -> str:
    key = hashlib.sha256(f"{video_url}#t={start}".encode("utf-8")).hexdigest()
    return f"{POSTER_PREFIX}{key[:20]}.webp"


def ffmpeg_command(video_url: str, start: float) -> list[str]:
    return [
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        str(start),
        "-i",
        video_url,
        "-frames:v",
        "1",
        "-vf",
        f"scale={POSTER_WIDTH}:-2",
        "-c:v",
        "libwebp",
        # Half the size of a JPEG of the same frame, with no visible loss.
        "-quality",
        "80",
        "-compression_level",
        "6",
        "-f",
        "image2pipe",
        "pipe:1",
    ]


def cut_poster(video_url: str, start: float) -> bytes:
    """The WebP of the frame at ``start``. ffmpeg reads the file over HTTP
    in ranges, so only the index and the frames around ``start`` are
    fetched."""
    result = subprocess.run(
        ffmpeg_command(video_url, start),
        capture_output=True,
        timeout=_CUT_TIMEOUT_S,
        check=True,
    )
    if not result.stdout:
        raise RuntimeError(f"ffmpeg wrote no frame for {video_url}#t={start}")
    return result.stdout


def poster_maker(
    env: Optional[str] = None,
    bucket: Optional["Bucket"] = None,
    cut: Callable[[str, float], bytes] = cut_poster,
) -> Optional[PosterMaker]:
    """Cuts and uploads posters into the env's bucket; None without ffmpeg,
    so the run publishes everything else and the next run tries again."""
    if cut is cut_poster and shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found; debate cards get no poster this run")
        return None
    target: Any = (
        bucket if bucket is not None else storage_client().bucket(bucket_for_env(env))
    )

    def make(video_url: str, start: float) -> Optional[str]:
        path = poster_path(video_url, start)
        try:
            blob = target.blob(path)
            if not blob.exists():
                data = cut(video_url, start)
                blob.cache_control = POSTER_CACHE_CONTROL
                blob.upload_from_string(
                    data, content_type="image/webp", predefined_acl="publicRead"
                )
        except Exception as exc:  # noqa: BLE001 — one poster never stops a run
            logger.warning("No poster for %s#t=%s: %s", video_url, start, exc)
            return None
        return storage_url(path, env)

    return make
