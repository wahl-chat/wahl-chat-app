# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
ManifestoUploadsConnector — party manifestos we received as files, not via AW.

Ingests uploaded PDFs
(``public/{context_id}/{doc_class}/{party_id}/{name}_{date}.pdf``) into
the same ``party_manifesto`` corpus as AW, tagged ``source="upload"``. Election +
party come from the object path; region/level/publish_date are derived from the
Firestore fixtures (hard-fail rather than default), since a wrong value would make
a chunk silently unreachable at query time.

AW overlap is ONE policy with TWO triggers, and only ``wahlprogramm`` documents are
ever eligible — a Satzung or Grundsatzprogramm is not something AW publishes:

  * here, per document, on every run: a Wahlprogramm whose AW copy exists normalises
    to ``[]``, which the runner turns into a footprint delete. This covers the
    upload-arrives-second order and is the idempotent backstop for the other.
  * ``connectors/manifestos/supersede.py``, from AW's ``post_upsert``: retires the
    same documents the moment AW publishes them, which is the common order (parties
    send drafts before AW lists the final text) and avoids waiting a run.

Both decide per document from its class folder, never from a party+region+date
filter, so neither can remove a document the AW copy does not replace.
"""

from __future__ import annotations

import logging
import os
from datetime import date as date_type
from datetime import datetime, time, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from src.ingestion.chunking import chunk_pages
from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.manifesto_uploads.election_fixtures import (
    ElectionFixture,
    FixtureLookupError,
    load_election,
)
from src.ingestion.connectors.manifesto_uploads.mappers.corpus import (
    UPLOAD_SOURCE,
    build_upload_manifesto_records,
)
from src.ingestion.connectors.manifesto_uploads.storage_paths import (
    UploadPathError,
    parse_object_path,
    parse_upload,
    staging_path,
    storage_url,
)
from src.ingestion.schemas import ChunkRecord, SourceType

logger = logging.getLogger(__name__)

# Env var pointing at an alternative manifest (absolute or repo-relative).
_MANIFEST_ENV = "MANIFESTO_UPLOADS_MANIFEST"

# Selects the work-list backend: "manifest" (default) or "bucket". See work_list.
_SOURCE_ENV = "MANIFESTO_UPLOADS_SOURCE"

# Optional election-date floor (ISO YYYY-MM-DD). See resolve_since_floor.
_SINCE_ENV = "MANIFESTO_UPLOADS_SINCE"


class ManifestUnavailable(RuntimeError):
    """The manifest file backing the work-list does not exist.

    Deliberately distinct from an EMPTY work-list: an absent file is a
    misconfiguration (wrong ENV, manifest not shipped in the image), while an
    empty-but-present manifest is a real "nothing should exist" that retires the
    stored uploads. Conflating the two would let a bad deploy wipe the uploaded
    corpus. Mirrors BucketListingError for the bucket backend.
    """


class OverlapCheckUnavailable(RuntimeError):
    """The Abgeordnetenwatch-overlap check could not be completed.

    Raised rather than assuming "no AW copy": failing open writes a duplicate that
    no later run cleans up, because the next healthy run's guard fires and
    normalize() then deliberately preserves the stored upload. Surfaced as a
    per-item failure so the document is simply retried on the next run.
    """


def resolve_since_floor(value: Optional[str] = None) -> Optional[date_type]:
    """Resolve the election-date floor (``value``, else ``MANIFESTO_UPLOADS_SINCE``).

    No floor by default. Raises ValueError on an unparseable date — a misconfigured
    floor should fail loudly, not silently scope the run.
    """
    raw = value if value is not None else os.getenv(_SINCE_ENV)
    if raw is None or not raw.strip():
        return None
    try:
        return date_type.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"{_SINCE_ENV} must be an ISO date (YYYY-MM-DD), got {raw!r}"
        ) from exc


def in_scope(
    object_path: str, since: Optional[date_type], env: Optional[str] = None
) -> bool:
    """Whether *object_path* is on/after *since* (no floor → always in scope).

    An unresolvable election/party also counts as in scope: the floor must not
    become a way to silently swallow a broken path — that fails loudly in
    normalize() instead.
    """
    if since is None:
        return True
    try:
        ref = parse_object_path(object_path)
        fixture = load_election(ref.context_id, env)
    except (UploadPathError, FixtureLookupError):
        return True
    return fixture.election_date >= since


def default_manifest_path(env: Optional[str] = None) -> Path:
    """Return the manifest path for *env* (defaults to ``$ENV``, else dev)."""
    override = os.getenv(_MANIFEST_ENV)
    if override:
        return Path(override).expanduser()
    resolved = (env or os.getenv("ENV") or "dev").strip().lower()
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "manifesto_uploads"
        / f"{resolved}.txt"
    )


def load_manifest(path: Optional[Path] = None, env: Optional[str] = None) -> list[str]:
    """Read the manifest into normalised, de-duplicated object paths.

    A missing manifest raises ManifestUnavailable (an empty result would be read as
    "retire everything"); an empty-but-present one legitimately returns []. A
    malformed line raises UploadPathError — silently skipping it would leave a
    document un-ingested with no signal.
    """
    manifest = path or default_manifest_path(env)
    if not manifest.exists():
        raise ManifestUnavailable(
            f"no upload manifest at {manifest} — refusing to treat a missing file as "
            "an empty work-list, which would retire every uploaded manifesto in the "
            "corpus. Create the file (an empty one is a valid 'nothing should exist') "
            "or set MANIFESTO_UPLOADS_SOURCE=bucket"
        )

    seen: dict[str, None] = {}
    for lineno, raw in enumerate(
        manifest.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            ref = parse_upload(line)
        except UploadPathError as exc:
            raise UploadPathError(f"{manifest}:{lineno}: {exc}") from exc
        seen.setdefault(ref.object_path, None)
    return list(seen)


def work_list(
    manifest_path: Optional[Path] = None, env: Optional[str] = None
) -> list[str]:
    """Return the object paths that SHOULD exist, per ``MANIFESTO_UPLOADS_SOURCE``.

    Default reads the checked-in manifest; ``"bucket"`` lists the live bucket
    instead, since the manifest ships inside the image and wouldn't see a new
    upload until redeploy. Either way this is a complete desired-state list, so a
    document dropped from it gets retired (see ``discover()``).

    Raises ManifestUnavailable / BucketListingError when the backing store cannot be
    read — never degrades to an empty list, which would read as "retire everything".
    """
    source = (os.getenv(_SOURCE_ENV) or "manifest").strip().lower()
    if source == "manifest":
        return load_manifest(manifest_path, env)
    if source == "bucket":
        # Imported lazily so the manifest path never needs a Storage client.
        from src.ingestion.connectors.manifesto_uploads.bucket_listing import (  # noqa: PLC0415
            list_uploaded_objects,
        )

        return list_uploaded_objects(env)
    raise ValueError(
        f"{_SOURCE_ENV}={source!r} is not a known work-list backend; "
        "expected 'manifest' or 'bucket'"
    )


def load_pdf_pages(object_path: str, env: Optional[str] = None) -> dict:
    """Read one PDF and return its page-annotated text.

    Prefers the local staging copy so a document can be reviewed before upload;
    falls back to the bucket (the Cloud Run path). Raises ValueError on any
    read/parse failure, with a message suitable for a skip log.
    """
    # pypdf is a heavy parser dep; keep the import local so importing this module
    # (e.g. for the registry) never pulls it in.
    import pypdf  # noqa: PLC0415

    local = staging_path(object_path)
    if local.exists():
        try:
            data = local.read_bytes()
        except OSError as exc:
            raise ValueError(f"could not read staged file {local}: {exc}") from exc
        read_from = str(local)
    else:
        url = storage_url(object_path, env)
        try:
            import requests  # noqa: PLC0415

            resp = requests.get(
                url, timeout=120, headers={"User-Agent": "wahl.chat-ingest"}
            )
            resp.raise_for_status()
            data = resp.content
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"download failed for {url}: {exc}") from exc
        read_from = url

    try:
        reader = pypdf.PdfReader(BytesIO(data))
        pages = [
            (page_no, page.extract_text() or "")
            for page_no, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"PDF parse failed for {object_path}: {exc}") from exc

    return {"pages": pages, "total_pages": len(pages), "read_from": read_from}


class ManifestoUploadsConnector(BaseConnector):
    """Connector for operator-uploaded manifesto PDFs.

    discover(since) → fetch → normalize → [runner embeds + upserts]

    ``since`` is ignored: the work-list (see ``work_list()``) is already a complete
    statement of what should exist, so every entry is offered every run and the
    content-hash guard skips unchanged ones cheaply.
    """

    source_type: str = SourceType.PARTY_MANIFESTO.value
    source: str = UPLOAD_SOURCE

    def __init__(
        self,
        manifest_path: Optional[Path] = None,
        env: Optional[str] = None,
        since: Optional[date_type] = None,
    ) -> None:
        self._manifest_path = manifest_path
        self._env = env
        self._since = since if since is not None else resolve_since_floor()
        # The desired state resolved by the last discover(), whichever backend
        # produced it. fetch() reads it to tell a live document from a retired one.
        self._expected_paths: set[str] = set()
        # An EMPTY _expected_paths is only meaningful as "retire everything" once
        # discover() has actually resolved a work-list; before that it is just an
        # un-initialised default, so fetch() must not read it as a retirement.
        self._discovered = False

    # ------------------------------------------------------------------
    # Election-date scoping
    # ------------------------------------------------------------------

    def _in_scope(self, object_path: str) -> bool:
        """Whether *object_path* passes this connector's election-date floor."""
        return in_scope(object_path, self._since, self._env)

    # ------------------------------------------------------------------
    # discover — the work-list plus stored documents it no longer names
    # ------------------------------------------------------------------

    def _stored_object_paths(self) -> set[str]:
        """Object paths of uploaded documents already stored (empty if no store bound).

        Lets a document dropped from the work-list still be visited and retired.
        """
        qdrant = self._store_client
        if qdrant is None:
            return set()

        from qdrant_client import models as qdrant_models  # noqa: PLC0415

        from src.ingestion.setup_collection import COLLECTION_NAME  # noqa: PLC0415

        collection = self._store_collection or COLLECTION_NAME
        scroll_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="source_type",
                    match=qdrant_models.MatchValue(value=self.source_type),
                ),
                qdrant_models.FieldCondition(
                    key="source", match=qdrant_models.MatchValue(value=self.source)
                ),
            ]
        )
        found: set[str] = set()
        next_offset = None
        while True:
            points, next_offset = qdrant.scroll(
                collection_name=collection,
                scroll_filter=scroll_filter,
                limit=1000,
                offset=next_offset,
                with_payload=["meta.storage_object_path"],
                with_vectors=False,
            )
            for point in points:
                path = ((point.payload or {}).get("meta") or {}).get(
                    "storage_object_path"
                )
                if isinstance(path, str) and path:
                    found.add(path)
            if next_offset is None:
                break
        return found

    def discover(self, since: Optional[int]) -> list[str]:
        """Return object paths to process: the work-list, plus retired leftovers.

        ``since`` is accepted for the ABC contract and ignored (see class
        docstring).
        """
        named = set(work_list(self._manifest_path, self._env))
        self._expected_paths = {p for p in named if self._in_scope(p)}
        # Set only after work_list() returned — a listing failure raises, leaving
        # the flag False so no half-resolved state can drive a retirement.
        self._discovered = True

        skipped = named - self._expected_paths
        if skipped:
            logger.info(
                "%d document(s) below the %s election-date floor — not ingested, "
                "and their stored chunks are left untouched: %s",
                len(skipped),
                self._since,
                ", ".join(sorted(skipped)),
            )

        # Retire only in-scope documents — an out-of-scope one is "not now", not
        # "should not exist", and must never be deleted just because a floor is set.
        retired = {
            p
            for p in self._stored_object_paths()
            if p not in named and self._in_scope(p)
        }
        if retired:
            logger.info(
                "%d uploaded document(s) no longer in the work-list — retiring: %s",
                len(retired),
                ", ".join(sorted(retired)),
            )
        return sorted(self._expected_paths | retired)

    # ------------------------------------------------------------------
    # fetch — read + parse one document (never raises; defers to normalize)
    # ------------------------------------------------------------------

    def fetch(self, external_id: str) -> dict:
        """Read and parse one uploaded PDF, or flag it retired/skipped.

        Failures return as ``skip_reason`` rather than raising (the runner doesn't
        wrap fetch(); normalize() surfaces the skip instead).
        """
        object_path = external_id

        # Not in the work-list → retire. Guarded on discover() having run rather
        # than on a non-empty work-list: an empty desired state is a legitimate
        # "nothing should exist", and is the only way the LAST stored upload can
        # ever be retired. An empty bucket listing is already refused upstream
        # (bucket_listing.list_uploaded_objects) unless the bucket is truly empty.
        if self._discovered and object_path not in self._expected_paths:
            return {"object_path": object_path, "retired": True}

        try:
            content = load_pdf_pages(object_path, self._env)
        except ValueError as exc:
            return {"object_path": object_path, "skip_reason": str(exc)}
        return {"object_path": object_path, **content}

    # ------------------------------------------------------------------
    # AW-already-has-it check — re-run every run, for Wahlprogramme only, so the
    # retirement is idempotent instead of a one-shot event on the AW side
    # ------------------------------------------------------------------

    def _aw_copy_exists(self, *, party_id: str, fixture: ElectionFixture) -> bool:
        """Whether an AW-sourced manifesto already covers this party and election.

        Only consulted for ``wahlprogramm`` documents (see normalize): party + region
        + election date identifies a programme, so it says nothing about whether AW
        replaces some other document of the same party.

        Returns False (proceed with the upload) when no store is bound — a dry run
        has nothing to compare against. Raises OverlapCheckUnavailable if the count
        itself fails, which must not be read as "no AW copy".
        """
        qdrant = self._store_client
        if qdrant is None:
            return False

        from qdrant_client import models as qdrant_models  # noqa: PLC0415

        from src.ingestion.setup_collection import COLLECTION_NAME  # noqa: PLC0415

        day_start = datetime.combine(
            fixture.election_date, time.min, tzinfo=timezone.utc
        )
        day_end = datetime.combine(fixture.election_date, time.max, tzinfo=timezone.utc)
        try:
            found = qdrant.count(
                collection_name=self._store_collection or COLLECTION_NAME,
                count_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="source_type",
                            match=qdrant_models.MatchValue(value=self.source_type),
                        ),
                        qdrant_models.FieldCondition(
                            key="party_id",
                            match=qdrant_models.MatchValue(value=party_id),
                        ),
                        qdrant_models.FieldCondition(
                            key="region",
                            match=qdrant_models.MatchValue(value=fixture.region),
                        ),
                        qdrant_models.FieldCondition(
                            key="publish_date",
                            range=qdrant_models.DatetimeRange(
                                gte=day_start, lte=day_end
                            ),
                        ),
                    ],
                    must_not=[
                        qdrant_models.FieldCondition(
                            key="source",
                            match=qdrant_models.MatchValue(value=self.source),
                        )
                    ],
                ),
                exact=True,
            ).count
        except Exception as exc:  # noqa: BLE001
            raise OverlapCheckUnavailable(
                f"could not check for an Abgeordnetenwatch copy of "
                f"{party_id}/{fixture.context_id}: {exc}"
            ) from exc
        return found > 0

    # ------------------------------------------------------------------
    # normalize — validate against the fixtures, chunk, build records
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords for one uploaded document from fetch()'s output.

        Empty list = retired (runner cleans up). Raises ValueError for anything
        else that went wrong, which keeps the stored copy intact — only a
        deliberate empty-list retirement removes chunks.
        """
        object_path: str = raw["object_path"]

        if raw.get("retired"):
            return []

        skip_reason = raw.get("skip_reason")
        if skip_reason:
            raise ValueError(f"{object_path}: {skip_reason}")

        try:
            ref = parse_object_path(object_path)
            fixture = load_election(ref.context_id, self._env)
        except (UploadPathError, FixtureLookupError) as exc:
            raise ValueError(str(exc)) from exc

        # AW parity applies to Wahlprogramme ONLY. AW's catalogue carries election
        # programmes, so nothing it publishes replaces a Satzung or a federal
        # Grundsatzprogramm — those are ingested whatever AW holds for the party.
        if ref.is_wahlprogramm:
            # A failed overlap check is a retryable per-item failure, NOT a licence to
            # write: the runner reports it and re-offers the document next run.
            try:
                aw_carries_it = self._aw_copy_exists(
                    party_id=ref.party_id, fixture=fixture
                )
            except OverlapCheckUnavailable as exc:
                raise ValueError(
                    f"{object_path}: {exc} — not ingesting this run"
                ) from exc

            if aw_carries_it:
                # Authoritative empty result: the runner retires exactly THIS
                # document's footprint. Deciding per document, on every run, is what
                # makes the cleanup automatic AND safe — it can never reach a sibling
                # upload that the AW copy does not replace, which a filter keyed on
                # party+region+election date would.
                logger.warning(
                    "retiring uploaded Wahlprogramm %s — Abgeordnetenwatch now carries "
                    "this programme (party=%s region=%s election=%s) and is the citable "
                    "public source. Drop the manifest line (or the bucket object) to "
                    "stop re-checking it.",
                    object_path,
                    ref.party_id,
                    fixture.region,
                    fixture.election_date,
                )
                return []

        chunk_tuples = chunk_pages(raw["pages"])
        if not chunk_tuples:
            raise ValueError(
                f"{object_path}: no extractable text — the PDF is likely scanned "
                "images and needs OCR before it can be ingested"
            )

        try:
            records = build_upload_manifesto_records(
                ref=ref,
                fixture=fixture,
                chunks=list(chunk_tuples),
                citation_url=ref.citation_url(self._env),
                total_pages=raw.get("total_pages"),
            )
        except FixtureLookupError as exc:
            raise ValueError(str(exc)) from exc

        if not records:
            raise ValueError(f"{object_path}: produced no records")
        return records
