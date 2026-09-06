# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Storage-triggered ingestion for uploaded party PDFs — the event-driven
complement to the daily ``ingest-manifesto-uploads`` Cloud Run reconcile job.

Same orchestration as the legacy V1 triggers (one function per event, one
document per invocation), but ZERO duplicated pipeline: the ``ingestion`` and
``wahlchat-common`` packages are installed from wheels built at deploy time
(see ``predeploy.sh``),
and each event runs the real ``manifesto_uploads`` connector through the real
runner via ``ingestion.connectors.manifesto_uploads.single``. The legacy
codebase in ``functions/`` targets the retired per-context collections and
skips the five-segment layout on purpose.

Config: firebase params (deploy-time prompts / .env.<project> files) are copied
into os.environ before any ingestion import happens — the package freezes
EMBEDDING_MODEL/DIM/COLLECTION_NAME from the environment at import time, which
is why every ingestion import below sits inside a handler, after
``_export_params()``.
"""

import os

from firebase_functions import logger, storage_fn
from firebase_functions.options import MemoryOption, SupportedRegion
from firebase_functions.params import StringParam

ENV = StringParam("ENV")  # "dev" or "prod"
QDRANT_URL = StringParam("QDRANT_URL")
QDRANT_API_KEY = StringParam("QDRANT_API_KEY")
EMBEDDING_PROVIDER = StringParam("EMBEDDING_PROVIDER", default="")
EMBEDDING_MODEL = StringParam("EMBEDDING_MODEL", default="")
EMBEDDING_DIM = StringParam("EMBEDDING_DIM", default="")
OPENAI_API_KEY = StringParam("OPENAI_API_KEY", default="")
GOOGLE_API_KEY = StringParam("GOOGLE_API_KEY", default="")
VERTEX_SA_JSON = StringParam("VERTEX_SA_JSON", default="")
VERTEX_PROJECT_ID = StringParam("VERTEX_PROJECT_ID", default="")
VERTEX_LOCATION = StringParam("VERTEX_LOCATION", default="")

# The trigger must live where the bucket lives: the prod Firebase bucket is
# US-hosted (same reason the legacy triggers deploy to US_EAST1), dev is EU.
_is_prod = (
    os.getenv("ENV", "dev") == "prod"
    or os.getenv("GCLOUD_PROJECT", os.getenv("GCP_PROJECT", "")) == "wahl-chat"
)
_REGION = SupportedRegion.US_EAST1 if _is_prod else SupportedRegion.EUROPE_WEST1


def _export_params() -> None:
    """Copy resolved params into os.environ for the ingestion package (and the
    SDK clients that self-read, e.g. OPENAI_API_KEY). Empty values are skipped
    so an unused optional param never shadows a real ambient variable."""
    for key, param in (
        ("ENV", ENV),
        ("QDRANT_URL", QDRANT_URL),
        ("QDRANT_API_KEY", QDRANT_API_KEY),
        ("EMBEDDING_PROVIDER", EMBEDDING_PROVIDER),
        ("EMBEDDING_MODEL", EMBEDDING_MODEL),
        ("EMBEDDING_DIM", EMBEDDING_DIM),
        ("OPENAI_API_KEY", OPENAI_API_KEY),
        ("GOOGLE_API_KEY", GOOGLE_API_KEY),
        ("VERTEX_SA_JSON", VERTEX_SA_JSON),
        ("VERTEX_PROJECT_ID", VERTEX_PROJECT_ID),
        ("VERTEX_LOCATION", VERTEX_LOCATION),
    ):
        value = param.value
        if value:
            os.environ[key] = value
    # The bundle carries no seed files: fixtures come from live Firestore.
    os.environ.setdefault("ELECTION_FIXTURES_SOURCE", "firestore")


def _parse_or_skip(name: str):  # noqa: ANN202
    """Parse the object path, or return None for objects this codebase ignores
    (context icons, legacy four-segment uploads, non-PDFs) — an event for a
    foreign object is routine, not an error. Called after _export_params()."""
    from ingestion.connectors.manifesto_uploads.storage_paths import (  # noqa: PLC0415
        UploadPathError,
        parse_object_path,
    )

    try:
        return parse_object_path(name)
    except UploadPathError as exc:
        logger.info(f"skipping {name}: {exc}")
        return None


def _ensure_public(bucket_name: str, object_path: str) -> None:
    """Make the object publicly readable BEFORE ingestion — citations are plain
    GCS URLs governed by object ACLs, and the connector downloads via that same
    public URL. The make target applies publicRead at copy time; this covers
    uploads from the Firebase console. Best-effort: on failure the download
    (and the citation) 403s, which surfaces as the run's per-item error."""
    from google.cloud import storage  # noqa: PLC0415

    try:
        storage.Client().bucket(bucket_name).blob(object_path).make_public()
    except Exception as exc:  # noqa: BLE001
        logger.warn(f"could not make {object_path} public: {exc}")


def _report_or_raise(kind: str, name: str, report) -> None:  # noqa: ANN001
    """Log the RunReport; a per-item failure must fail the function loudly
    (run_connector only warns), so the error is visible and the event retried
    by the daily reconcile at the latest."""
    if report.failed_ids:
        raise RuntimeError(f"{kind} {name} failed: {report.failed_ids}")
    logger.info(
        f"{kind} {name}: processed={report.processed} "
        f"chunks_upserted={report.chunks_upserted} "
        f"present_skips={report.present_skips}"
    )


@storage_fn.on_object_finalized(
    region=_REGION,
    timeout_sec=540,
    memory=MemoryOption.GB_1,
    # Bounds concurrent embedding spend when a whole election's PDFs land at
    # once; the queue drains serially and the daily job reconciles any event
    # that expires undelivered.
    max_instances=3,
)
def ingest_uploaded_pdf(
    event: storage_fn.CloudEvent[storage_fn.StorageObjectData],
) -> None:
    """Chunk, embed and index one uploaded party PDF into the V2 corpus."""
    _export_params()
    name = event.data.name or ""
    if _parse_or_skip(name) is None:
        return
    if event.data.content_type != "application/pdf":
        logger.info(f"skipping {name}: content type {event.data.content_type}")
        return

    _ensure_public(event.data.bucket, name)

    from ingestion.connectors.manifesto_uploads.single import (  # noqa: PLC0415
        ingest_one,
    )

    _report_or_raise("ingest", name, ingest_one(name))


@storage_fn.on_object_deleted(
    region=_REGION,
    timeout_sec=300,
    memory=MemoryOption.MB_512,
)
def retire_uploaded_pdf(
    event: storage_fn.CloudEvent[storage_fn.StorageObjectData],
) -> None:
    """Retire one deleted party PDF's chunks from the V2 corpus."""
    _export_params()
    name = event.data.name or ""
    if _parse_or_skip(name) is None:
        return

    # An OVERWRITE also fires on_object_deleted (for the replaced generation).
    # Retiring then would race the finalize event that is ingesting the new
    # bytes — so retire only when the object is actually gone.
    from google.cloud import storage as gcs  # noqa: PLC0415

    if gcs.Client().bucket(event.data.bucket).get_blob(name) is not None:
        logger.info(f"skipping retire of {name}: object still exists (overwrite)")
        return

    from ingestion.connectors.manifesto_uploads.single import (  # noqa: PLC0415
        retire_one,
    )

    _report_or_raise("retire", name, retire_one(name))
