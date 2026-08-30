#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Bust the Next.js data cache for seeded Firestore data.

The hosted app caches election config (contexts, parties, sources,
questions) by tag. After a real-project seed, call this so a newly added
election does not stay empty.

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


# Coarse tags still attached on the web cache (covers entries written before
# per-context tags). Also busted so a deploy mid-seed cannot leave both.
COARSE_CACHE_TAGS = (
    "contexts",
    "context_parties",
    "proposed_questions",
    "source_documents",
)
DEFAULT_SITE_URLS = {
    "prod": "https://wahl.chat",
    "dev": "https://dev.wahl.chat",
}
# Same aliases as firebase/.firebaserc. Used so a seed that wrote via ADC
# cannot flush the other deployment's cache.
EXPECTED_FIRESTORE_PROJECTS = {
    "prod": "wahl-chat",
    "dev": "wahl-chat-dev",
}
VERCEL_ENV_VARS_URL = "https://vercel.com/wahl-chat/web/settings/environment-variables"


class RevalidateConfigError(Exception):
    """Secret or site URL is missing — nothing was sent."""


class RevalidateProjectMismatchError(RevalidateConfigError):
    """Firestore project does not match ENV — refuse to flush the other site."""


class RevalidateRequestError(Exception):
    """The /api/revalidate request failed."""


def resolved_firestore_project(explicit: str | None = None) -> str | None:
    """Project the seed just wrote to, if we can tell.

    Prefer the Firestore client the caller already used. Fall back to the
    initialized Firebase app — not GOOGLE_CLOUD_PROJECT, which is often
    leftover from local `.env` / `gcloud config` and would block a
    standalone flush of the other deployment.
    """
    if explicit:
        return explicit
    try:
        import firebase_admin  # noqa: PLC0415

        return firebase_admin.get_app().project_id or None
    except (ImportError, ValueError):
        return None


def ensure_project_matches_env(firestore_project: str | None = None) -> None:
    """Refuse to pick a site URL when the write went to a different project.

    `ENV` selects both the fixture set and the default deployment
    (wahl.chat vs dev.wahl.chat). ADC can point the Firestore client at
    the other project, so a seed would flush the wrong cache.
    """
    actual = resolved_firestore_project(firestore_project)
    expected = EXPECTED_FIRESTORE_PROJECTS.get(_env())
    if actual is None or expected is None or actual == expected:
        return
    site = DEFAULT_SITE_URLS.get(_env()) or f"ENV={_env()}"
    raise RevalidateProjectMismatchError(
        f"Firestore project {actual!r} does not match ENV={_env()} "
        f"(expected {expected!r}). Not revalidating {site} so a seed "
        "cannot flush the other deployment."
    )


def site_url() -> str | None:
    """Public origin of the Next.js app whose cache we must bust.

    REVALIDATE_URL / SITE_URL win; otherwise ENV=prod → wahl.chat and
    ENV=dev → dev.wahl.chat.
    """
    explicit = os.getenv("REVALIDATE_URL") or os.getenv("SITE_URL")
    if explicit:
        return explicit.rstrip("/")
    return DEFAULT_SITE_URLS.get(_env())


def seed_cache_tags(context_ids: list[str]) -> list[str]:
    tags = list(COARSE_CACHE_TAGS)
    for context_id in context_ids:
        tags.extend(
            [
                f"context:{context_id}",
                f"context:{context_id}:parties",
                f"context:{context_id}:sources",
                f"context:{context_id}:questions",
            ]
        )
    return tags


def revalidate_payload(context_ids: list[str]) -> dict[str, list[str]]:
    return {"tags": seed_cache_tags(context_ids)}


def context_ids_from_fixtures() -> list[str]:
    contexts_file = _data_dir() / "contexts.json"
    if not contexts_file.exists():
        raise RevalidateConfigError(f"contexts file not found: {contexts_file}")
    with open(contexts_file) as f:
        contexts = json.load(f)
    return list(contexts)


def post_revalidate(
    context_ids: list[str], firestore_project: str | None = None
) -> str:
    """POST tags and context paths to /api/revalidate. Returns the response body."""
    # Use the REVALIDATE_SECRET of the matching Vercel deployment
    # (Production vs Preview/Development):
    # https://vercel.com/wahl-chat/web/settings/environment-variables
    ensure_project_matches_env(firestore_project)
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

    print(f"  tags={len(payload['tags'])} ({body})")
    return body


def missing_secret_warning() -> str:
    script = "firebase/scripts/revalidate_frontend_cache.py"
    return (
        "============================================================\n"
        " Frontend cache was not revalidated.\n"
        " Firestore is written, but the hosted app may keep a cached\n"
        " empty party list until that tag is busted or the 24h safety\n"
        " TTL expires.\n"
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
        description="Bust the hosted app's election-config data cache after a seed.",
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
