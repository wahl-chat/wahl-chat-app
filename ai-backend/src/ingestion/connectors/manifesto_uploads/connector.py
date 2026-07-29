# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
ManifestoUploadsConnector — party manifestos we received as files, not via an API.

Parties send their programmes directly for upcoming elections, and communal
elections often have no Abgeordnetenwatch coverage at all. Those PDFs are uploaded
to the public Storage bucket under ``public/{context_id}/{party_id}/{name}_{date}.pdf``;
a manifest lists which of them are live, and this connector ingests them into the
same ``party_manifesto`` corpus as the AW catalogue, carrying ``source="upload"``.

Everything retrieval-critical is DERIVED, never declared:
  * election + party come from the object path;
  * region, level and publish_date come from the Firestore seed fixtures for that
    election (``election_fixtures``), which hard-fail rather than default.

Manifest semantics
------------------
The manifest is the full statement of what should exist. Each run discovers both
the manifest entries AND the documents already stored, so a line REMOVED from the
manifest is still visited, normalises to zero chunks, and has its footprint deleted
by the runner — retiring a document is a one-line edit, not a manual cleanup.

Citations always point at the bucket URL for the object, even on a local run that
reads the staged copy: the staged file and the uploaded object are the same bytes,
so the ``#page=`` anchor is exact either way.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

from src.ingestion.chunking import chunk_pages
from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.manifesto_uploads.election_fixtures import (
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
    """Read the manifest and return normalised object paths, de-duplicated.

    One entry per line; blank lines and ``#`` comments are ignored. An entry may be
    a public URL, a ``gs://`` URI, a staging path or a bare object path — all
    normalise to the same object path, so a line does not have to be rewritten when
    the file moves from staging to the bucket.

    A missing manifest is not an error (nothing to ingest yet); a malformed LINE is,
    since silently skipping it would leave a document quietly un-ingested.

    Raises:
        UploadPathError: If a non-comment line cannot be normalised.
    """
    manifest = path or default_manifest_path(env)
    if not manifest.exists():
        logger.warning("no upload manifest at %s — nothing to ingest", manifest)
        return []

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
    """Return the object paths that SHOULD exist in the corpus.

    Backend is chosen by ``MANIFESTO_UPLOADS_SOURCE``:
      * unset / ``"manifest"`` (default) — the checked-in list. Reviewable in a
        diff, needs no credentials, and is what a local run uses.
      * ``"bucket"`` — list the bucket prefix. The manifest ships inside the
        container image, so a scheduled Job reading it would not see a new upload
        until the next deploy; listing the bucket makes an upload or a deletion take
        effect on the next run instead.

    Either way the result is a complete desired-state statement, which is what lets
    a document dropped from it be retired (see ManifestoUploadsConnector.discover).

    Raises:
        UploadPathError:     A malformed manifest line.
        BucketListingError:  The bucket could not be listed (whole-run failure —
                             never degraded to an empty list, which would read as
                             "retire everything").
        ValueError:          An unknown backend name.
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

    Prefers the local staging copy (``firebase/storage_data/{object_path}``) so a
    document can be ingested and reviewed before it is uploaded; falls back to
    downloading the bucket object, which is the path a Cloud Run job takes.

    Returns:
        ``{"pages": [(page_no, text)], "total_pages": int, "read_from": str}``.

    Raises:
        ValueError: On any read/parse failure — the message is suitable for a skip log.
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

    ``since`` is ignored: the work-list is a complete statement of what should
    exist, so every entry is offered every run and the runner's content-hash guard
    skips the unchanged ones cheaply without consuming the batch budget. A cursor
    would only be able to hide entries.

    The work-list comes from the manifest by default, or from a bucket listing when
    ``MANIFESTO_UPLOADS_SOURCE=bucket`` (see ``work_list``). Everything downstream is
    identical either way — including retirement, so on the bucket backend deleting
    the object is what removes its chunks.
    """

    source_type: str = SourceType.PARTY_MANIFESTO.value
    source: str = UPLOAD_SOURCE

    def __init__(
        self, manifest_path: Optional[Path] = None, env: Optional[str] = None
    ) -> None:
        self._manifest_path = manifest_path
        self._env = env
        # The desired state resolved by the last discover(), whichever backend
        # produced it. fetch() reads it to tell a live document from a retired one.
        self._expected_paths: set[str] = set()

    # ------------------------------------------------------------------
    # discover — the work-list plus stored documents it no longer names
    # ------------------------------------------------------------------

    def _stored_object_paths(self) -> set[str]:
        """Return object paths of uploaded documents already in the store.

        Read so that a document dropped from the work-list is still visited and can
        be retired. Returns an empty set when no store is bound (the runner binds
        one before discover; a bare unit-test instance has none).
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

        Args:
            since: Accepted for the ABC contract and ignored (see class docstring).

        Returns:
            Sorted object paths. Documents present in the store but absent from the
            work-list are included so ``normalize()`` can retire them.
        """
        self._expected_paths = set(work_list(self._manifest_path, self._env))
        retired = self._stored_object_paths() - self._expected_paths
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

        Failures are returned as ``skip_reason`` rather than raised, mirroring the
        manifesto connector: the runner does not wrap fetch(), so the skip is
        surfaced from normalize() where run_connector skip-and-continues.

        Args:
            external_id: Bucket-relative object path (as returned by discover()).

        Returns:
            ``{"object_path", "pages", "total_pages", "read_from"}``, or a dict
            carrying ``retired``/``skip_reason``.
        """
        object_path = external_id

        # Not in the current work-list → retire it (normalize returns no chunks and
        # the runner deletes the stored footprint). Guarded on a non-empty work-list:
        # an empty one means discovery found nothing to keep, and retiring the whole
        # uploaded corpus off the back of that is never the intent.
        if self._expected_paths and object_path not in self._expected_paths:
            return {"object_path": object_path, "retired": True}

        try:
            content = load_pdf_pages(object_path, self._env)
        except ValueError as exc:
            return {"object_path": object_path, "skip_reason": str(exc)}
        return {"object_path": object_path, **content}

    # ------------------------------------------------------------------
    # normalize — validate against the fixtures, chunk, build records
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Build ChunkRecords for one uploaded document.

        Args:
            raw: Dict returned by fetch().

        Returns:
            One ChunkRecord per chunk; an EMPTY list for a retired document, which
            the runner treats as an authoritative empty result and cleans up.

        Raises:
            ValueError: If fetch flagged a skip, the path or election/party cannot
                        be resolved, or the document yields no text. Raising keeps
                        the stored copy intact — only a deliberate retirement
                        (empty list) removes chunks.
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
