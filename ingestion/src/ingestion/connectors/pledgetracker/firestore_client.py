# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Firestore client for the PledgeTracker runner.

Same credential order as the API server: a service-account JSON in the
working directory wins, then anonymous credentials when
``FIRESTORE_EMULATOR_HOST`` is set, otherwise Application Default Credentials.
Built with ``google-cloud-firestore`` rather than ``firebase_admin`` so the
job image does not carry the chat service's admin SDK. The document API
(``collection`` / ``document`` / ``get`` / ``set(merge=True)`` / ``stream`` /
``delete``) is the same one the runner was written against.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.cloud.firestore import Client


def _credentials_path() -> Path:
    name = (
        "wahl-chat-firebase-adminsdk.json"
        if os.getenv("ENV") == "prod"
        else "wahl-chat-dev-firebase-adminsdk.json"
    )
    return Path(name)


def _project_id() -> str | None:
    return (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or os.getenv("FIREBASE_PROJECT_ID")
    )


def firestore_client() -> Client:
    """Return a Firestore client for the target selected by the current env.

    Call this only after the accidental-write guard has run. The client reads
    ``FIRESTORE_EMULATOR_HOST`` at construction time.
    """
    credentials_path = _credentials_path()
    emulator = bool(os.getenv("FIRESTORE_EMULATOR_HOST"))
    if credentials_path.exists():
        from google.oauth2 import service_account

        info = json.loads(credentials_path.read_text(encoding="utf-8"))
        creds = service_account.Credentials.from_service_account_info(info)
        return Client(project=info.get("project_id"), credentials=creds)
    if emulator:
        from google.auth.credentials import AnonymousCredentials

        return Client(
            project=_project_id() or "demo-wahl-chat",
            credentials=AnonymousCredentials(),
        )
    project = _project_id()
    return Client(project=project) if project else Client()
