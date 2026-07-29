# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Bucket-listing work-list for the uploaded-manifesto connector (deployed path).

The manifest is baked into the container image, so a scheduled Job would only
notice a newly uploaded PDF after a redeploy. Listing the bucket instead makes the
BUCKET the statement of what should exist: a file that appears is ingested on the
next run, and a file that is deleted is retired by the same reconcile that a
removed manifest line triggers. That is the behaviour the old upload-triggered
function had, without a second ingestion implementation.

Selected explicitly via ``MANIFESTO_UPLOADS_SOURCE=bucket``; the manifest stays the
default so local runs and CI need no bucket credentials. See
``connector.work_list``.

Non-conforming objects are SKIPPED, not fatal
---------------------------------------------
``public/`` is a shared prefix — context icons and other public assets live there
too, and it is readable by anyone. Anything that is not a
``public/{election}/{party}/{name}_{YYYY-MM-DD}.pdf`` is therefore logged and
ignored rather than failing the run, because an unrelated asset appearing in the
bucket must not stop every manifesto from being ingested. A PDF sitting in the
right shape but naming an unknown election or party still fails loudly later, in
the per-document validation gate.
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

    NOT a ValueError: this is a whole-run failure (no work-list could be built),
    not a per-document data problem. Letting it surface unwrapped from discover()
    aborts the run loudly instead of silently reconciling against an empty
    work-list — which, since an empty list means "nothing should exist", would
    retire every uploaded document in the corpus.
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

    Args:
        env:    Environment selecting the bucket; defaults to ``$ENV`` then dev.
        client: Storage client override (tests).

    Returns:
        Sorted, de-duplicated object paths that parse as uploaded manifestos.

    Raises:
        BucketListingError: If the bucket cannot be listed, or if it contains
            objects but none of them are manifestos. The second case is treated as
            a failure rather than an empty work-list because "the bucket has
            content but I recognised none of it" is far more likely a wrong bucket
            or a changed layout than a deliberate removal of every document — and
            an empty work-list would retire the entire uploaded corpus.
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
            "match 'public/{election}/{party}/{name}_YYYY-MM-DD.pdf'. Refusing to "
            "treat this as an empty work-list, which would retire every uploaded "
            "manifesto in the corpus"
        )

    logger.info(
        "bucket work-list: %d manifesto(s) under gs://%s/%s",
        len(found),
        bucket_name,
        UPLOAD_PREFIX,
    )
    return sorted(found)
