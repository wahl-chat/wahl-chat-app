# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Integration tests for the Firestore seed script against the local emulator.

Covers:
  - The top-level `contexts` collection, plus the `parties` and
    `proposed_questions` sub-collections under a seeded context, are each
    populated with at least one document after running seed_firestore.py.
    The seed script writes only these paths — the other top-level V2
    collections moved to the ingestion pipeline / Qdrant ChunkRecords and
    are no longer seeded.
  - wahl_swiper_theses / wahl_swiper_results V1 documents are NOT cleared
    or overwritten by the V2 seed (additive-only guarantee).

Both tests skip cleanly when the Firestore emulator is not reachable at
localhost:8081 (run `make stores-up` to start the emulator).
"""

import os
import socket
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Module-level emulator availability guard
# ---------------------------------------------------------------------------

_EMULATOR_HOST = "localhost"
_EMULATOR_PORT = 8081


def _emulator_reachable() -> bool:
    """Return True if the Firestore emulator port is accepting connections."""
    try:
        with socket.create_connection((_EMULATOR_HOST, _EMULATOR_PORT), timeout=2):
            return True
    except OSError:
        return False


if not _emulator_reachable():
    pytest.skip(
        "Firestore emulator not running — run `make stores-up` to start it "
        "(fires firebase emulators:start --only firestore on port 8081)",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_SEED_SCRIPT = os.path.join(_REPO_ROOT, "firebase", "scripts", "seed_firestore.py")
_FIRESTORE_EMULATOR_HOST = f"{_EMULATOR_HOST}:{_EMULATOR_PORT}"
_PROJECT_ID = "demo-wahl-chat"

# Top-level collection the seed script populates (`seed_contexts`). The
# `parties` and `proposed_questions` sub-collections live under each seeded
# context document (the previously-asserted top-level V2 collections
# are no longer seeded).
_CONTEXTS_COLLECTION = "contexts"

# V1 collections that must be untouched by the V2 seed.
_V1_SENTINEL_COLLECTION = "wahl_swiper_theses"
_V1_SENTINEL_DOC = "v1-sentinel"

# ---------------------------------------------------------------------------
# Firestore admin client helper (module-level, initialised once per session)
# ---------------------------------------------------------------------------

_FIREBASE_APP = None


def _get_db():
    """Return a Firestore client against the local emulator.

    Initialises the Firebase Admin SDK once (or reuses the existing app) using
    anonymous emulator credentials — no real GCP credentials needed.
    """
    global _FIREBASE_APP  # noqa: PLW0603

    import firebase_admin
    from firebase_admin import credentials, firestore
    import google.auth.credentials

    class _EmulatorCredentials(credentials.Base):
        def get_credential(self):
            return google.auth.credentials.AnonymousCredentials()

    if _FIREBASE_APP is None:
        try:
            _FIREBASE_APP = firebase_admin.get_app()
        except ValueError:
            _FIREBASE_APP = firebase_admin.initialize_app(
                _EmulatorCredentials(),
                options={"projectId": _PROJECT_ID},
            )

    return firestore.client()


def _run_seed() -> subprocess.CompletedProcess:
    """Run seed_firestore.py against the local emulator and return the result."""
    env = {**os.environ, "FIRESTORE_EMULATOR_HOST": _FIRESTORE_EMULATOR_HOST}
    return subprocess.run(
        [sys.executable, _SEED_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_seed_v2_collections():
    """The seed script populates contexts + its parties / proposed_questions.

    Runs seed_firestore.py as a subprocess with FIRESTORE_EMULATOR_HOST set,
    then uses the firebase-admin client to assert that what the seed script
    actually writes today is non-empty:
      - the top-level `contexts` collection,
      - the `parties` sub-collection under a seeded context,
      - the `proposed_questions` sub-collection under a seeded context.
    An empty collection after seeding indicates a fixture or seed-function bug.
    """
    result = _run_seed()
    assert result.returncode == 0, (
        "seed_firestore.py exited non-zero — seeding failed. "
        f"stderr: {result.stderr[:1000]}\nstdout: {result.stdout[:1000]}"
    )

    db = _get_db()

    # Assert against the collections seed_firestore.py genuinely writes
    # (contexts + parties/proposed_questions sub-collections), not the
    # top-level collections the script no longer seeds.
    context_docs = list(db.collection(_CONTEXTS_COLLECTION).limit(1).stream())
    assert len(context_docs) >= 1, (
        f"Collection '{_CONTEXTS_COLLECTION}' has no documents after seeding. "
        f"Expected at least 1 context. Seed stdout tail: {result.stdout[-500:]}"
    )
    context_id = context_docs[0].id

    party_docs = list(
        db.collection(_CONTEXTS_COLLECTION)
        .document(context_id)
        .collection("parties")
        .limit(1)
        .stream()
    )
    assert len(party_docs) >= 1, (
        f"Sub-collection 'contexts/{context_id}/parties' has no documents after "
        f"seeding. Expected at least 1 party. "
        f"Seed stdout tail: {result.stdout[-500:]}"
    )

    # proposed_questions is seeded as nested paths
    # (proposed_questions/{party}/questions/{question_id}), so the direct
    # children of the `proposed_questions` collection are ancestor-only
    # documents that hold sub-collections but no fields. Firestore's `.stream()`
    # skips such missing-ancestor documents, so list references with
    # `list_documents()` (which does include them) to prove the collection was
    # populated.
    proposed_question_docs = list(
        db.collection(_CONTEXTS_COLLECTION)
        .document(context_id)
        .collection("proposed_questions")
        .list_documents()
    )
    assert len(proposed_question_docs) >= 1, (
        f"Sub-collection 'contexts/{context_id}/proposed_questions' has no "
        f"documents after seeding. Expected at least 1 proposed question. "
        f"Seed stdout tail: {result.stdout[-500:]}"
    )


def test_v1_untouched():
    """V1 wahl_swiper_* documents survive a V2 seed run unchanged.

    Writes a sentinel document into wahl_swiper_theses before running the V2
    seed, then asserts the sentinel still exists afterwards. This proves the
    seed functions are additive-only and do not delete or overwrite V1 data.
    """
    db = _get_db()

    # Write a sentinel document into the V1 collection BEFORE seeding.
    sentinel_data = {"sentinel": True, "kind": "v1-guard"}
    db.collection(_V1_SENTINEL_COLLECTION).document(_V1_SENTINEL_DOC).set(sentinel_data)

    # Verify the sentinel was written successfully.
    before_snap = db.collection(_V1_SENTINEL_COLLECTION).document(_V1_SENTINEL_DOC).get()
    assert before_snap.exists, (
        f"Failed to write sentinel doc to {_V1_SENTINEL_COLLECTION}/{_V1_SENTINEL_DOC} "
        "before seed run — emulator write issue, not a seed bug"
    )

    # Run the V2 seed.
    result = _run_seed()
    assert result.returncode == 0, (
        "seed_firestore.py exited non-zero during the sentinel run. "
        f"stderr: {result.stderr[:1000]}\nstdout: {result.stdout[:1000]}"
    )

    # Assert the sentinel document still exists unchanged after seeding.
    after_snap = db.collection(_V1_SENTINEL_COLLECTION).document(_V1_SENTINEL_DOC).get()
    assert after_snap.exists, (
        f"Sentinel document {_V1_SENTINEL_COLLECTION}/{_V1_SENTINEL_DOC} was deleted "
        "or lost after the V2 seed run (additive-only guarantee violated). "
        f"Seed stdout: {result.stdout[:500]}"
    )

    after_data = after_snap.to_dict()
    assert after_data == sentinel_data, (
        f"Sentinel document data was modified by the V2 seed run. "
        f"Before: {sentinel_data!r}  After: {after_data!r}. "
        f"Seed stdout: {result.stdout[:500]}"
    )
