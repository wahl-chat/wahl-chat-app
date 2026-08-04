# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Bucket-listing work-list for the uploaded-manifesto connector (deployed path,
``MANIFESTO_UPLOADS_SOURCE=bucket``; manifest stays the default — see
``connector.work_list``).

Makes the BUCKET the statement of what should exist: an upload is ingested on the
next run, a deletion retires it — no second ingestion implementation.

Non-conforming objects (context icons, other ``public/`` assets) are skipped, not
fatal. A PDF in the right shape but naming an unknown election/party still fails
loudly later, in the per-document validation gate.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

from src.ingestion.connectors.manifesto_uploads.storage_paths import (
    UploadPathError,
    bucket_for_env,
    parse_object_path,
)

if TYPE_CHECKING:
    from google.cloud.storage import Client

logger = logging.getLogger(__name__)

# Only this prefix is listed: it is the documented upload location and the only
# publicly readable one (see firebase/storage.rules).
UPLOAD_PREFIX = "public/"


class BucketListingError(RuntimeError):
    """The bucket could not be listed.

    NOT a ValueError (a per-item skip signal) — this is a whole-run failure, left
    unwrapped from discover() so the run aborts loudly instead of silently
    reconciling against an empty work-list, which would retire every document.
    """


def _client(env: Optional[str] = None) -> "Client":
    """Return a Storage client using Application Default Credentials."""
    from google.cloud.storage import Client  # noqa: PLC0415

    project = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or os.getenv("FIREBASE_PROJECT_ID")
    )
    return Client(project=project) if project else Client()


def list_uploaded_objects(
    env: Optional[str] = None, client: Optional["Client"] = None
) -> list[str]:
    """List the uploaded manifesto PDFs in the bucket for *env*.

    Raises BucketListingError if the bucket can't be listed, or has content but
    none of it parses as a manifesto — more likely a wrong bucket than a
    deliberate clear-out, and an empty work-list would retire the whole corpus.
    """
    bucket_name = bucket_for_env(env)
    storage_client = client if client is not None else _client(env)

    try:
        blobs = list(storage_client.list_blobs(bucket_name, prefix=UPLOAD_PREFIX))
    except Exception as exc:  # noqa: BLE001
        raise BucketListingError(
            f"could not list gs://{bucket_name}/{UPLOAD_PREFIX}: {exc}"
        ) from exc

    found: dict[str, None] = {}
    skipped: list[str] = []
    for blob in blobs:
        name = getattr(blob, "name", "") or ""
        # Directory placeholder objects that some tools create.
        if not name or name.endswith("/"):
            continue
        try:
            parse_object_path(name)
        except UploadPathError:
            skipped.append(name)
            continue
        found[name] = None

    if skipped:
        logger.info(
            "ignored %d object(s) under %s that are not uploaded manifestos: %s",
            len(skipped),
            UPLOAD_PREFIX,
            ", ".join(sorted(skipped)[:10]) + (" …" if len(skipped) > 10 else ""),
        )

    if not found and blobs:
        raise BucketListingError(
            f"gs://{bucket_name}/{UPLOAD_PREFIX} holds {len(blobs)} object(s) but none "
            "match 'public/{election}/{wahlprogramme|parteidokumente}/{party}/"
            "{name}_YYYY-MM-DD.pdf'. Refusing to treat this as an empty work-list, "
            "which would retire every uploaded manifesto in the corpus"
        )

    logger.info(
        "bucket work-list: %d manifesto(s) under gs://%s/%s",
        len(found),
        bucket_name,
        UPLOAD_PREFIX,
    )
    return sorted(found)
