# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Accidental-write guard shared by the CLIs that write Firestore directly."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def guard_firestore_target(job_name: str, allow_remote: bool = False) -> None:
    """Prevent ACCIDENTAL non-emulator writes outside prod.

    ENV=prod targets real Firestore. Every other ENV requires the emulator
    unless ``allow_remote`` is set explicitly — the deliberate path for writing
    into the deployed ENV Firebase project (typically the hosted dev
    environment).

    ``allow_remote`` unsets ``FIRESTORE_EMULATOR_HOST``: local ``.env`` and the
    Makefile routinely set it for emulator-mode development, and
    ``firebase_service`` keys off that variable at import time. Leaving it in
    place would make the flag a no-op and keep writing to the emulator. Call
    this BEFORE importing ``src.firebase_service``.
    """
    if allow_remote:
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
    env = os.getenv("ENV", "dev")
    if env == "prod" or os.getenv("FIRESTORE_EMULATOR_HOST"):
        return
    if allow_remote:
        logger.warning(
            "%s writing to REMOTE Firestore with ENV=%s (--allow-remote).",
            job_name,
            env,
        )
        return
    raise RuntimeError(
        f"FIRESTORE_EMULATOR_HOST is required for {job_name} when ENV is not "
        "prod. Set it to localhost:8081 for local runs, or pass --allow-remote "
        "to write into a deployed dev environment on purpose."
    )
