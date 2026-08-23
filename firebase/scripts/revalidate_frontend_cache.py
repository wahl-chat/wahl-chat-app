#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Bust the Next.js ISR cache for seeded Firestore data.

The live site caches contexts and parties for about an hour. After a
real-project seed, call this so a newly added election does not stay empty.

Usage (from the repo root or firebase/):

    REVALIDATE_SECRET=... ENV=prod python scripts/revalidate_frontend_cache.py
    REVALIDATE_SECRET=... ENV=dev python scripts/revalidate_frontend_cache.py

    # One election only:
    REVALIDATE_SECRET=... ENV=prod python scripts/revalidate_frontend_cache.py \\
        --context abgeordnetenhauswahl-berlin-2026

Use the REVALIDATE_SECRET of the matching Vercel deployment
(Production vs Preview/Development):
https://vercel.com/wahl-chat/web/settings/environment-variables
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
FIREBASE_DIR = SCRIPT_DIR.parent


def _env() -> str:
    return os.getenv("ENV", "dev")


def _data_dir() -> Path:
    return FIREBASE_DIR / "firestore_data" / _env()


# Tags the web app attaches to unstable_cache / ISR for the collections the
# seed script writes.
SEED_CACHE_TAGS = (
    "contexts",
    "context_parties",
    "proposed_questions",
    "source_documents",
)
DEFAULT_SITE_URLS = {
    "prod": "https://wahl.chat",
    "dev": "https://dev.wahl.chat",
}
VERCEL_ENV_VARS_URL = "https://vercel.com/wahl-chat/web/settings/environment-variables"


class RevalidateConfigError(Exception):
    """Secret or site URL is missing — nothing was sent."""


class RevalidateRequestError(Exception):
    """The /api/revalidate request failed."""


def site_url() -> str | None:
    """Public origin of the Next.js app whose cache we must bust.

    REVALIDATE_URL / SITE_URL win; otherwise ENV=prod → wahl.chat and
    ENV=dev → dev.wahl.chat.
    """
    explicit = os.getenv("REVALIDATE_URL") or os.getenv("SITE_URL")
    if explicit:
        return explicit.rstrip("/")
    return DEFAULT_SITE_URLS.get(_env())


def revalidate_payload(context_ids: list[str]) -> dict[str, list[str]]:
    paths = ["/"]
    for context_id in context_ids:
        paths.append(f"/{context_id}")
        paths.append(f"/{context_id}/sources")
    return {"tags": list(SEED_CACHE_TAGS), "paths": paths}


def context_ids_from_fixtures() -> list[str]:
    contexts_file = _data_dir() / "contexts.json"
    if not contexts_file.exists():
        raise RevalidateConfigError(f"contexts file not found: {contexts_file}")
    with open(contexts_file) as f:
        contexts = json.load(f)
    return list(contexts)


def post_revalidate(context_ids: list[str]) -> str:
    """POST tags and context paths to /api/revalidate. Returns the response body."""
    # Use the REVALIDATE_SECRET of the matching Vercel deployment
    # (Production vs Preview/Development):
    # https://vercel.com/wahl-chat/web/settings/environment-variables
    secret = os.getenv("REVALIDATE_SECRET")
    site = site_url()
    if not secret or not site:
        raise RevalidateConfigError(
            "Set REVALIDATE_SECRET to the value for this deployment "
            "(Production for ENV=prod, Preview/Development for ENV=dev). "
            f"Copy it from {VERCEL_ENV_VARS_URL}. "
            "Override the target with SITE_URL or REVALIDATE_URL if needed."
        )

    payload = revalidate_payload(context_ids)
    url = f"{site}/api/revalidate"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    print(f"Revalidating frontend cache at {url} ...")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RevalidateRequestError(
            f"Cache revalidation failed ({exc.code}): {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RevalidateRequestError(
            f"Cache revalidation failed: {exc.reason}"
        ) from exc

    print(f"  tags={payload['tags']} paths={len(payload['paths'])} ({body})")
    return body


def missing_secret_warning() -> str:
    script = "firebase/scripts/revalidate_frontend_cache.py"
    return (
        "============================================================\n"
        " Frontend cache was not revalidated.\n"
        " Firestore is written, but the live site may keep serving the\n"
        " previous hour's cached pages — a newly added context can look\n"
        " empty (no parties to select) until ISR expires.\n"
        "\n"
        " Bust the cache when you are ready:\n"
        f"   REVALIDATE_SECRET=... ENV={_env()} python {script}\n"
        "\n"
        " Copy the REVALIDATE_SECRET of that deployment (Production\n"
        " for ENV=prod / wahl.chat, Preview or Development for ENV=dev\n"
        " / dev.wahl.chat) from:\n"
        f"   {VERCEL_ENV_VARS_URL}\n"
        "============================================================"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bust the wahl.chat ISR cache for seeded Firestore data.",
    )
    parser.add_argument(
        "--context",
        action="append",
        dest="contexts",
        metavar="CONTEXT_ID",
        help="Revalidate this context (repeatable). Default: every id in contexts.json.",
    )
    args = parser.parse_args(argv)

    try:
        context_ids = args.contexts or context_ids_from_fixtures()
        post_revalidate(context_ids)
    except (RevalidateConfigError, RevalidateRequestError) as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        if isinstance(exc, RevalidateConfigError):
            print(missing_secret_warning(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
