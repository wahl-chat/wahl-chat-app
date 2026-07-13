# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
AW-linked external program documents -> party_manifesto corpus.

Implements two public functions:
  - ingest_programs(db, polls, bucket) — fetch external program docs linked from
    AW polls and write them as party_manifesto SourceItemRecords to source_items/.
  - chunk_program(source_item, raw) — worker-compatible 2-arg chunker that splits
    a stored program text into deterministic ChunkRecords for embedding.

Design decisions:
  - SourceItemRecord written to source_items/ with vector_status="pending";
    the embedding worker will pick it up and call chunk_program via the
    PARTY_MANIFESTO dispatcher branch added to worker.py.
  - Verbatim program bytes stored to GCS via gcs.store_original before
    writing source_item — the worker re-loads raw from GCS at chunk time.
  - ingest_programs receives db as an argument — never calls _get_db() itself.
  - db writes use .set() — unconditional overwrite = idempotent upsert.

Security notes:
  SSRF guard: ``field_related_links[].uri`` is upstream-
  controlled content from the AW API.  Scheme filtering alone is NOT an SSRF
  mitigation.  Before any network call, ``_is_safe_program_url`` enforces a
  strict host allow-list (``_ALLOWED_PROGRAM_HOSTS``), resolves the host and
  rejects any private / loopback / link-local / reserved IP (blocks the cloud
  metadata service and RFC-1918 hosts), and ``requests.get`` is called with
  ``allow_redirects=False`` so an allow-listed host cannot 302 into an internal
  address.  "entity:node/..." internal Drupal refs are skipped
  before any network call.

  Corpus injection: SourceItemRecord uses extra="forbid"; raw bytes
  stored verbatim to GCS (never executed); chunk_program extracts text only.

  GDPR Art. 9 wall: this module does NOT access users/{uid}, writes only
  to source_items/ and GCS, and has no QSP writes (structural guarantee).

  Mis-routing guard: PARTY_MANIFESTO is wired to chunk_program in
  worker.chunk_source_item; a missing-branch regression will fail CI.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
from datetime import date
from typing import Any
from urllib.parse import urlparse

import requests

# gcs.py deleted — programs.py is a deferred module
# (not wired to the active connector pipeline).  gcs is stubbed to None so
# import-time crashes are avoided; ingest_programs() will raise AttributeError
# if called, which is the expected failure mode for a deferred feature.
# This module will be rewritten to ChunkRecord / Qdrant pattern in a future phase.
gcs = None  # type: ignore[assignment]  # deferred module: gcs.py deleted
from src.ingestion.ids import compute_source_item_id, make_chunk_key  # noqa: E402
try:
    from src.ingestion.schemas import (  # type: ignore[attr-defined]
        AuthorityTier,
        ChunkRecord,
        SourceItemRecord,
        SourceType,
    )
except ImportError:
    AuthorityTier = None  # type: ignore[assignment, misc]
    ChunkRecord = None  # type: ignore[assignment, misc]
    SourceItemRecord = None  # type: ignore[assignment, misc]
    SourceType = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chunking constants
# ---------------------------------------------------------------------------

# Fixed-size character window for splitting program text into chunks.
# 1500 chars is a comfortable context-window size for embedding (no LLM used).
_CHUNK_SIZE = 1500
# Character overlap between consecutive chunks (sliding window).
_CHUNK_OVERLAP = 150

# HTTP fetch timeout (seconds) — prevents unbounded hangs on slow program URLs.
_HTTP_TIMEOUT = 30

# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------

# Strict host allow-list for program-document fetches.  Only documents linked
# from these trusted AW domains are fetched.  Tightening this (rather than an
# open IP-range check) is acceptable for this milestone — the corpus client
# already pins the AW host, and program links come from the AW API.
_ALLOWED_PROGRAM_HOSTS = frozenset(
    {
        "www.abgeordnetenwatch.de",
        "abgeordnetenwatch.de",
    }
)


def _is_safe_program_url(uri: str) -> bool:
    """Return True only for http(s) URLs on an allow-listed host that resolves
    to a public IP (SSRF guard).

    Rejects:
      - non-http(s) schemes and host-less URIs;
      - hosts not in ``_ALLOWED_PROGRAM_HOSTS``;
      - hosts that resolve to a private / loopback / link-local / reserved IP
        (blocks the cloud metadata service at 169.254.169.254 and RFC-1918
        internal hosts even if DNS is poisoned);
      - resolution failures (fail closed).

    Note: callers MUST still pass ``allow_redirects=False`` to ``requests.get``
    so an allow-listed host cannot 302-redirect into an internal address after
    this check passes.
    """
    parsed = urlparse(uri)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if parsed.hostname.lower() not in _ALLOWED_PROGRAM_HOSTS:
        return False
    try:
        for info in socket.getaddrinfo(parsed.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_programs(
    db: Any,
    polls: list[dict],
    bucket: str,
) -> list[SourceItemRecord]:
    """Fetch AW-linked external program documents and write them as party_manifesto corpus items.

    For each poll in `polls`, iterates ``poll["field_related_links"]`` and fetches
    only links that pass ``_is_safe_program_url`` (SSRF guard): http(s)
    scheme, an allow-listed host, and a host that resolves to a public IP.
    Fetches use ``allow_redirects=False`` so an allow-listed host cannot redirect
    into an internal address.  ``entity:node/...`` internal Drupal refs and any
    URL failing the guard are skipped without any network result being stored.

    Each fetched external program is:
    1. Stored verbatim to GCS (idempotent overwrite).
    2. Written as a ``SourceItemRecord`` (source_type=PARTY_MANIFESTO,
       authority_tier=SELF_REPORTED, vector_status="pending") to source_items/
       keyed by its deterministic source_item_id (.set()).

    Zero stance-pair documents are written (structural guarantee — no
    stance-pair modules are imported or called in this module).

    Args:
        db:     Firestore client handle (passed by caller).
        polls:  List of raw poll dicts from the AW API.  Each must have
                ``"id"`` (int), ``"field_poll_date"`` (ISO date str), and
                optionally ``"field_related_links"`` (list of link dicts).
        bucket: GCS bucket name for storage_ref construction.

    Returns:
        List of ``SourceItemRecord`` instances written to Firestore (one per
        successfully fetched http(s) program link).
    """
    written: list[SourceItemRecord] = []

    for poll in polls:
        poll_id: int = poll["id"]
        poll_date_str: str = poll.get("field_poll_date") or ""
        links: list[dict] = poll.get("field_related_links") or []

        # SourceItemRecord.publish_date is required and the corpus must be
        # deterministic (no wall-clock).  If the poll has no parseable ISO date,
        # skip the whole poll with a warning rather than fabricating date.today().
        try:
            publish_date = date.fromisoformat(poll_date_str)
        except (ValueError, TypeError):
            logger.warning(
                "programs: skipping poll_id=%s — unparseable field_poll_date=%r "
                "(publish_date is required; not fabricating date.today() — WR-07)",
                poll_id,
                poll_date_str,
            )
            continue

        # Keep only URLs that pass the full SSRF guard (scheme +
        # host allow-list + public-IP resolution), not just the scheme prefix.
        safe_links = [
            (idx, link)
            for idx, link in enumerate(links)
            if _is_safe_program_url(link.get("uri", ""))
        ]
        # Audit the rejected http(s) links so a blocked SSRF attempt is visible.
        for idx, link in enumerate(links):
            uri = link.get("uri", "")
            if uri.startswith(("https://", "http://")) and not _is_safe_program_url(uri):
                logger.warning(
                    "programs: rejected unsafe program uri=%s poll_id=%s idx=%s "
                    "(SSRF guard CR-01 — host not allow-listed or resolves to a "
                    "private/loopback/link-local IP)",
                    uri,
                    poll_id,
                    idx,
                )

        for idx, link in safe_links:
            uri = link["uri"]
            external_id: str = f"aw_program:{poll_id}:{idx}"
            source_item_id = compute_source_item_id("party_manifesto", external_id)

            # ----------------------------------------------------------------
            # Fetch the program document (guarded uri; no redirects so an
            # allow-listed host cannot 302 into an internal address).
            # ----------------------------------------------------------------
            try:
                resp = requests.get(uri, timeout=_HTTP_TIMEOUT, allow_redirects=False)
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "programs: failed to fetch program uri=%s poll_id=%s idx=%s error=%s",
                    uri,
                    poll_id,
                    idx,
                    str(exc)[:200],
                )
                continue

            program_text: str = resp.text or ""
            raw_payload: dict = {"uri": uri, "content": program_text}
            raw_bytes: bytes = json.dumps(raw_payload, ensure_ascii=False).encode("utf-8")

            # ----------------------------------------------------------------
            # Store verbatim to GCS (idempotent overwrite)
            # ----------------------------------------------------------------
            blob_path: str = f"aw_programs/{poll_id}_{idx}.json"
            storage_ref: str = gcs.store_original(blob_path, raw_bytes, "application/json")  # type: ignore[attr-defined]

            # publish_date was parsed (and validated) once per poll above.

            # ----------------------------------------------------------------
            # Build SourceItemRecord and write to source_items/ (.set())
            # ----------------------------------------------------------------
            source_item = SourceItemRecord(
                source_item_id=source_item_id,
                source_type=SourceType.PARTY_MANIFESTO,
                external_id=external_id,
                party_id="unbekannt",  # AW polls are not party-keyed; consumer re-maps
                region="DE",
                region_path=["EU", "DE"],
                authority_tier=AuthorityTier.SELF_REPORTED,
                publish_date=publish_date,
                storage_ref=storage_ref,
                vector_status="pending",
            )
            db.collection("source_items").document(str(source_item_id)).set(
                source_item.model_dump(mode="json")
            )
            written.append(source_item)
            logger.info(
                "programs: wrote party_manifesto source_item source_item_id=%s poll_id=%s idx=%s",
                source_item_id,
                poll_id,
                idx,
            )

    return written


def chunk_program(source_item: SourceItemRecord, raw: dict) -> list[ChunkRecord]:
    """Produce deterministic ChunkRecords from a stored program text.

    This is the WORKER's chunker for PARTY_MANIFESTO items.  It has the SAME
    2-arg ``(source_item, raw)`` signature as ``chunk_poll`` (worker-dispatcher
    contract).

    The program text is split into fixed-size character windows with a small
    overlap.  Splitting is deterministic (no LLM, no wall-clock) so re-running
    with the same input always yields the same chunk keys (idempotency).

    Empty text produces an empty list (not an error).

    Args:
        source_item: The normalised ``SourceItemRecord`` for the program.
                     Must have ``source_item_id``, ``region``,
                     ``authority_tier``, ``source_type``, and ``publish_date``.
        raw:         The GCS-stored raw payload: ``{"uri": str, "content": str}``.

    Returns:
        A list of ``ChunkRecord`` instances with zero-based sequential indexes.
        Returns ``[]`` for empty or whitespace-only content.
    """
    content: str = raw.get("content") or ""
    text = content.strip()
    if not text:
        return []

    uri: str = raw.get("uri") or ""

    # Fixed-size character windows with overlap (deterministic, no regex, no LLM)
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        window = text[start:end].strip()
        if window:
            windows.append(window)
        start += _CHUNK_SIZE - _CHUNK_OVERLAP

    chunks: list[ChunkRecord] = []
    for chunk_index, window_text in enumerate(windows):
        chunk_key = make_chunk_key(source_item.source_item_id, chunk_index)
        chunks.append(
            ChunkRecord(
                chunk_key=chunk_key,
                source_item_id=source_item.source_item_id,
                chunk_index=chunk_index,
                text=window_text,
                party_id=source_item.party_id,
                region=source_item.region,
                authority_tier=source_item.authority_tier,
                source_type=source_item.source_type,
                publish_date=source_item.publish_date,
                citation_url=uri or None,
                citation_title=None,
            )
        )

    return chunks
