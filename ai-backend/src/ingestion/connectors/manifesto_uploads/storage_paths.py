# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
The upload path IS the metadata:
``public/{context_id}/{doc_folder}/{party_id}/{name}_{date}.pdf``.

Election, document class and party come from the path, not a declared field, so they
can't disagree with where the file lives. ``document_date`` (the filename suffix) is
kept in ``meta`` — NOT the chunk ``publish_date``, which is the ELECTION date
instead, matching AW-sourced manifestos so both land in the same campaign retrieval
window. ``citation_url`` always points at the bucket, even when bytes are read from
the local staging copy (same bytes, so the page anchor is exact either way).

The ``doc_folder`` segment exists to make the AW-overlap policy safe: only a
Wahlprogramm is the kind of document Abgeordnetenwatch itself publishes, so only a
Wahlprogramm may ever be retired because an AW copy appeared. Enforced in
``connector.py``'s ``normalize()``, via ``UploadRef.is_wahlprogramm``.
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

# Document classes. WAHLPROGRAMM is the election programme a party runs on — the
# same class AW's election-program catalogue carries, and therefore the only class an
# AW copy can supersede. PARTEIDOKUMENT is anything else we hold only BECAUSE a party
# published no Wahlprogramm (a federal Grundsatzprogramm, a Satzung); it is never
# retired automatically, since no AW document replaces it.
WAHLPROGRAMM = "wahlprogramm"
PARTEIDOKUMENT = "parteidokument"

# Folder segment → document class. The folder is the plural collection name, the
# stamped value is the singular class.
_DOC_TYPE_BY_FOLDER: dict[str, str] = {
    "wahlprogramme": WAHLPROGRAMM,
    "parteidokumente": PARTEIDOKUMENT,
}

_LAYOUT = (
    "public/{election}/{wahlprogramme|parteidokumente}/{party}/{name}_YYYY-MM-DD.pdf"
)

# public/{context_id}/{doc_folder}/{party_id}/{name}_{YYYY-MM-DD}.pdf
_OBJECT_RE = re.compile(
    r"^public/(?P<context_id>[^/]+)/(?P<doc_folder>[^/]+)/(?P<party_id>[^/]+)/"
    r"(?P<stem>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.pdf$",
    re.IGNORECASE,
)


class UploadPathError(ValueError):
    """An upload path does not carry the metadata the layout promises.

    ValueError subclass so the runner treats it as a per-item skip.
    """


@dataclass(frozen=True)
class UploadRef:
    """One uploaded manifesto, fully described by its object path."""

    object_path: str
    context_id: str
    party_id: str
    document_name: str
    document_date: date_type
    document_type: str

    @property
    def title(self) -> str:
        """Human-readable document title for citations ("Wahlprogramm SPD ...")."""
        return self.document_name.replace("-", " ").strip()

    @property
    def is_wahlprogramm(self) -> bool:
        """Whether an AW election programme could replace this document."""
        return self.document_type == WAHLPROGRAMM

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
    """Normalise a manifest entry (URL, ``gs://`` URI, staging path, or bare object
    path) to a bucket-relative object path — so a line works before and after
    upload. Raises UploadPathError if no ``public/...`` component is found.
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
        raise UploadPathError(f"{value!r} does not contain a '{_LAYOUT}' component")
    return raw[marker:]


def parse_object_path(object_path: str) -> UploadRef:
    """Parse a bucket-relative object path into its metadata.

    Raises UploadPathError on a shape/date mismatch — rejected rather than guessed,
    since a mis-segmented path would put a filename where the party key belongs.
    """
    match = _OBJECT_RE.match(object_path)
    if match is None:
        raise UploadPathError(
            f"{object_path!r} does not match '{_LAYOUT}' — file it under the document "
            "class folder and give it a date suffix"
        )
    try:
        document_date = date_type.fromisoformat(match.group("date"))
    except ValueError as exc:
        raise UploadPathError(
            f"{object_path!r} carries an invalid date {match.group('date')!r}"
        ) from exc

    # Rejected rather than defaulted to Wahlprogramm: a typo'd folder would
    # otherwise make a Satzung eligible for AW supersede.
    doc_folder = match.group("doc_folder").lower()
    try:
        document_type = _DOC_TYPE_BY_FOLDER[doc_folder]
    except KeyError:
        raise UploadPathError(
            f"{object_path!r} names an unknown document class folder {doc_folder!r}; "
            f"expected one of {sorted(_DOC_TYPE_BY_FOLDER)}"
        ) from None

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
        document_type=document_type,
    )


def parse_upload(value: str) -> UploadRef:
    """Normalise *value* to an object path and parse it (the common entry point)."""
    return parse_object_path(to_object_path(value))


def staging_path(object_path: str) -> Path:
    """Local staging location for an object path (for reads before/without upload).

    Resolved relative to this file so cwd does not matter.
    """
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "firebase" / "storage_data" / object_path
