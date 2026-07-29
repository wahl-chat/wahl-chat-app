# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
The upload path IS the metadata: ``public/{context_id}/{party_id}/{name}_{date}.pdf``.

Election and party are read off the path rather than declared anywhere, so the two
retrieval-critical fields cannot disagree with the file's location in the bucket.
The layout is the one the party-document upload flow has always used, so files
already in Storage parse unchanged.

Three things are derived here:
  * ``context_id`` / ``party_id`` — path segments, validated against the seed
    fixtures by ``election_fixtures``.
  * ``document_date``  — the ``_YYYY-MM-DD`` suffix, the document's own date. It is
    kept in ``meta`` and is NOT the chunk ``publish_date`` (that is the election
    date, matching how AW-sourced manifestos are stamped so both halves of
    ``party_manifesto`` sit in the same retrieval window).
  * ``citation_url``   — always the public bucket URL for this object, even when the
    bytes are read from the local staging copy. Citations must resolve to where the
    document actually lives, and the page anchor is exact because the staged file
    and the uploaded object are the same bytes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse

# Bucket host per environment. dev and prod differ only in the bucket name, which
# is why moving seed data between them is a find/replace on this prefix.
_BUCKETS: dict[str, str] = {
    "dev": "wahl-chat-dev.firebasestorage.app",
    "prod": "wahl-chat.firebasestorage.app",
}
_STORAGE_HOST = "https://storage.googleapis.com"

# public/{context_id}/{party_id}/{name}_{YYYY-MM-DD}.pdf
_OBJECT_RE = re.compile(
    r"^public/(?P<context_id>[^/]+)/(?P<party_id>[^/]+)/(?P<stem>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.pdf$",
    re.IGNORECASE,
)


class UploadPathError(ValueError):
    """An upload path does not carry the metadata the layout promises.

    ValueError subclass so the runner treats it as a per-item skip.
    """


@dataclass(frozen=True)
class UploadRef:
    """One uploaded manifesto, fully described by its object path.

    Attributes:
        object_path:   Bucket-relative path, ``public/{election}/{party}/{file}.pdf``.
        context_id:    Election segment.
        party_id:      Party segment (the corpus tenant key).
        document_name: Filename stem before the date suffix, hyphens intact.
        document_date: Date parsed from the filename suffix.
    """

    object_path: str
    context_id: str
    party_id: str
    document_name: str
    document_date: date_type

    @property
    def title(self) -> str:
        """Human-readable document title for citations ("Wahlprogramm SPD ...")."""
        return self.document_name.replace("-", " ").strip()

    def citation_url(self, env: Optional[str] = None) -> str:
        """Public URL of this object in the *env* bucket (percent-encoded)."""
        return storage_url(self.object_path, env)


def bucket_for_env(env: Optional[str] = None) -> str:
    """Return the Storage bucket for *env* (defaults to ``$ENV``, else dev)."""
    resolved = (env or os.getenv("ENV") or "dev").strip().lower()
    try:
        return _BUCKETS[resolved]
    except KeyError:
        raise UploadPathError(
            f"no Storage bucket configured for ENV={resolved!r}; "
            f"expected one of {sorted(_BUCKETS)}"
        ) from None


def storage_url(object_path: str, env: Optional[str] = None) -> str:
    """Build the public download URL for a bucket-relative *object_path*.

    Each path segment is percent-encoded individually so the slashes survive while
    spaces and umlauts in a filename do not break the link.
    """
    encoded = "/".join(quote(seg, safe="") for seg in object_path.split("/"))
    return f"{_STORAGE_HOST}/{bucket_for_env(env)}/{encoded}"


def to_object_path(value: str) -> str:
    """Normalise a manifest entry to a bucket-relative object path.

    Accepts a public Storage URL, a ``gs://bucket/...`` URI, a repo-relative
    staging path (``firebase/storage_data/public/...``), or the object path itself
    — so the same manifest line works before and after the file is uploaded.

    Raises:
        UploadPathError: If no ``public/...`` component can be found.
    """
    raw = value.strip()
    if not raw:
        raise UploadPathError("empty manifest entry")

    if raw.startswith(("http://", "https://")):
        raw = unquote(urlparse(raw).path).lstrip("/")
        # Strip the leading bucket name from a storage.googleapis.com style path.
        parts = raw.split("/", 1)
        if len(parts) == 2 and not parts[0].startswith("public"):
            raw = parts[1]
    elif raw.startswith("gs://"):
        raw = raw[len("gs://") :].split("/", 1)[-1]

    raw = raw.replace("\\", "/")
    marker = raw.find("public/")
    if marker == -1:
        raise UploadPathError(
            f"{value!r} does not contain a 'public/{{election}}/{{party}}/...' component"
        )
    return raw[marker:]


def parse_object_path(object_path: str) -> UploadRef:
    """Parse a bucket-relative object path into its metadata.

    Raises:
        UploadPathError: If the path does not match
            ``public/{election}/{party}/{name}_{YYYY-MM-DD}.pdf``, or the date is
            not a real calendar date. Both are rejected rather than guessed: the
            date ends up on the source card users read, and a mis-segmented path
            would put a filename where the party tenant key belongs.
    """
    match = _OBJECT_RE.match(object_path)
    if match is None:
        raise UploadPathError(
            f"{object_path!r} does not match "
            "'public/{election}/{party}/{name}_YYYY-MM-DD.pdf' — rename the file "
            "to carry its publication date"
        )
    try:
        document_date = date_type.fromisoformat(match.group("date"))
    except ValueError as exc:
        raise UploadPathError(
            f"{object_path!r} carries an invalid date {match.group('date')!r}"
        ) from exc

    stem = match.group("stem")
    if "/" in stem:
        raise UploadPathError(
            f"{object_path!r} nests the file deeper than one party folder"
        )

    return UploadRef(
        object_path=object_path,
        context_id=match.group("context_id"),
        party_id=match.group("party_id"),
        document_name=stem,
        document_date=document_date,
    )


def parse_upload(value: str) -> UploadRef:
    """Normalise *value* to an object path and parse it (the common entry point)."""
    return parse_object_path(to_object_path(value))


def staging_path(object_path: str) -> Path:
    """Local staging location for an object path, under firebase/storage_data/.

    Used to read the PDF bytes before the file is uploaded (and for offline runs).
    Resolved relative to this file so cwd does not matter.
    """
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "firebase" / "storage_data" / object_path
