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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ingestion.connectors.manifesto_uploads.bucket_listing import storage_client
from ingestion.connectors.manifesto_uploads.storage_paths import (
    bucket_for_env,
    storage_url,
)
from ingestion.feed.models import CardVideo, FeedItem

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
# One frame needs the file's index and a few seconds around ``start``; a cut
# that takes longer is a slow host, not a long file.
_CUT_TIMEOUT_S = 15
_ENCODERS_TIMEOUT_S = 10
# After this many failed cuts in a row the video host is down or too slow:
# every further cut would only wait out its timeout. The rest are cut next run.
MAX_FAILURES_IN_A_ROW = 3


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


def writes_webp() -> bool:
    """Whether the ffmpeg on the PATH can encode WebP. Some builds, such as
    Homebrew's, ship without libwebp, and would fail every cut."""
    if shutil.which("ffmpeg") is None:
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=_ENCODERS_TIMEOUT_S,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "libwebp" in result.stdout


def poster_maker(
    env: Optional[str] = None,
    bucket: Optional["Bucket"] = None,
    cut: Callable[[str, float], bytes] = cut_poster,
) -> PosterMaker:
    """Cuts and uploads posters into the env's bucket. Needs an ffmpeg that
    writes WebP (``writes_webp``)."""
    target = (
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


@dataclass
class PosterReport:
    written: dict[str, CardVideo] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)
    out_of_time: bool = False
    # Stopped after ``MAX_FAILURES_IN_A_ROW``.
    gave_up: bool = False


def add_posters(
    items: list[FeedItem],
    make_poster: PosterMaker,
    out_of_time: Callable[[], bool] = lambda: False,
) -> PosterReport:
    """Cut the poster of each published debate whose card video has none yet.
    ``written`` holds the card videos that now have one, by item id; a poster
    that could not be made is tried again next run."""
    report = PosterReport()
    in_a_row = 0
    for item in items:
        card = item.debate.card_video if item.debate is not None else None
        if item.status != "published" or card is None or card.poster_url:
            continue
        if out_of_time():
            report.out_of_time = True
            break
        if in_a_row >= MAX_FAILURES_IN_A_ROW:
            report.gave_up = True
            break
        poster_url = make_poster(card.video_url, card.start)
        if poster_url is None:
            report.failed.append(item.id)
            in_a_row += 1
            continue
        in_a_row = 0
        report.written[item.id] = card.model_copy(update={"poster_url": poster_url})
    return report
