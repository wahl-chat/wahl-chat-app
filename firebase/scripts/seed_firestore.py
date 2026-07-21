#!/usr/bin/env python3
"""
Seed Firestore with contexts, parties, and proposed questions data.

source_items, questions, question_stance_pairs, topics,
claims, and ingestion_watermarks collections are no longer seeded — those
data paths moved to Qdrant ChunkRecords.

Usage (from the firebase/ directory):
    FIRESTORE_EMULATOR_HOST=localhost:8081 python scripts/seed_firestore.py
    # or from the repo root:
    FIRESTORE_EMULATOR_HOST=localhost:8081 make seed-local

This script only ever seeds the LOCAL Firestore emulator. Production seeding
is intentionally blocked: the FIRESTORE_EMULATOR_HOST guard
below hard-exits when no emulator host is set, so the script can never write
to a real Firestore instance.

This script:
1. Imports all contexts from firestore_data/{env}/contexts.json
2. Imports parties from firestore_data/{env}/parties_{context_id}.json
   into contexts/{context_id}/parties sub-collection
3. Imports proposed questions from firestore_data/{env}/proposed_questions_{context_id}.json
   into contexts/{context_id}/proposed_questions sub-collection

File naming convention:
- contexts.json: Contains all context documents
- parties_{context_id}.json: Contains parties for a specific context
  Example: parties_bundestagswahl-2025.json -> contexts/bundestagswahl-2025/parties/
- proposed_questions_{context_id}.json: Contains proposed questions for a specific context
  Example: proposed_questions_kommunalwahl-muenchen-2026.json
           -> contexts/kommunalwahl-muenchen-2026/proposed_questions/
"""

import json
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

# --- Emulator guard ---
# Refuse to run unless the Firestore emulator host is explicitly set.
# This prevents accidental writes to production Firestore during local dev.
if not os.getenv("FIRESTORE_EMULATOR_HOST"):
    print(
        "\n"
        "============================================================\n"
        " ERROR: FIRESTORE_EMULATOR_HOST is not set.\n"
        " Refusing to seed — this would write to production Firestore.\n"
        "\n"
        " To seed the local emulator, run:\n"
        "   FIRESTORE_EMULATOR_HOST=localhost:8081 python seed_firestore.py\n"
        " or use the Makefile target:\n"
        "   make seed-local\n"
        "============================================================\n"
    )
    sys.exit(1)

# Configuration
ENV = os.getenv("ENV", "dev")
SCRIPT_DIR = Path(__file__).parent
FIREBASE_DIR = SCRIPT_DIR.parent
DATA_DIR = FIREBASE_DIR / "firestore_data" / ENV

def initialize_firebase():
    """Initialize Firebase Admin SDK against the Firestore emulator.

    This script only ever runs against the emulator (the FIRESTORE_EMULATOR_HOST
    guard above hard-exits otherwise), so it initializes with anonymous
    credentials + an explicit project id and performs NO Application Default
    Credentials lookup — the emulator needs no real credentials. This
    avoids failing when gcloud ADC is absent or expired.
    """
    import google.auth.credentials

    class _EmulatorCredentials(credentials.Base):
        """No-auth credential for the Firestore emulator."""

        def get_credential(self):
            return google.auth.credentials.AnonymousCredentials()

    project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or os.getenv("FIREBASE_PROJECT_ID")
        or "demo-wahl-chat"
    )
    print(
        f"Connecting to Firestore emulator at "
        f"{os.environ['FIRESTORE_EMULATOR_HOST']} (project: {project_id})"
    )
    firebase_admin.initialize_app(
        _EmulatorCredentials(), options={"projectId": project_id}
    )
    return firestore.client()


def seed_contexts(db):
    """Seed the contexts collection."""
    contexts_file = DATA_DIR / "contexts.json"

    if not contexts_file.exists():
        print(f"⚠️  Contexts file not found: {contexts_file}")
        return []

    with open(contexts_file) as f:
        contexts = json.load(f)

    print(f"\n📁 Seeding {len(contexts)} contexts...")
    print("-" * 60)

    context_ids = []
    for context_id, context_data in contexts.items():
        print(f"  ✅ {context_id}")
        db.collection("contexts").document(context_id).set(context_data)
        context_ids.append(context_id)

    print(f"\nContexts seeded: {len(context_ids)}")
    return context_ids


def seed_parties(db):
    """Seed parties sub-collections for each context."""
    # Find all party files matching pattern: parties_{context_id}.json
    party_files = list(DATA_DIR.glob("parties_*.json"))

    if not party_files:
        print("\n⚠️  No party files found")
        return

    print(f"\n📁 Found {len(party_files)} party files")
    print("-" * 60)

    total_parties = 0
    for party_file in sorted(party_files):
        # Extract context_id from filename: parties_{context_id}.json
        context_id = party_file.stem.replace("parties_", "")

        with open(party_file) as f:
            parties = json.load(f)

        print(f"\n  📂 {context_id} ({len(parties)} parties)")

        for party_id, party_data in parties.items():
            doc_ref = (
                db.collection("contexts")
                .document(context_id)
                .collection("parties")
                .document(party_id)
            )
            doc_ref.set(party_data)
            print(f"    ✅ {party_id}")
            total_parties += 1

    print(f"\nTotal parties seeded: {total_parties}")


def seed_proposed_questions(db) -> tuple[list, list]:
    """Seed proposed_questions sub-collections for each context.

    Returns (failed_files, failed_writes) so the caller can exit non-zero
    when anything failed.

    File naming convention:
    - proposed_questions_{context_id}.json: Contains proposed questions for a specific context
      Example: proposed_questions_kommunalwahl-muenchen-2026.json
               -> contexts/kommunalwahl-muenchen-2026/proposed_questions/

    The JSON structure uses paths like "proposed_questions/spd/questions/question_1"
    which gets stored as nested sub-collections under the context.
    """
    # Find all proposed questions files matching pattern: proposed_questions_*.json
    pq_files = list(DATA_DIR.glob("proposed_questions_*.json"))

    if not pq_files:
        print("\n⚠️  No proposed questions files found")
        return [], []

    print(f"\n📁 Found {len(pq_files)} proposed questions files")
    print("-" * 60)

    total_questions = 0
    failed_files = []
    failed_writes = []

    for pq_file in sorted(pq_files):
        # Extract context_id from filename: proposed_questions_{context_id}.json
        context_id = pq_file.stem.replace("proposed_questions_", "")

        try:
            with open(pq_file) as f:
                questions_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"\n  ❌ Failed to parse {pq_file.name}: {e}")
            failed_files.append((pq_file.name, str(e)))
            continue
        except OSError as e:
            print(f"\n  ❌ Failed to read {pq_file.name}: {e}")
            failed_files.append((pq_file.name, str(e)))
            continue

        print(f"\n  📂 {context_id} ({len(questions_data)} question entries)")

        for path, question_data in questions_data.items():
            # Path format: "proposed_questions/spd/questions/question_1"
            # We need to create this under contexts/{context_id}/
            path_parts = path.split("/")

            # Build the document reference under the context
            # contexts/{context_id}/proposed_questions/{party_id}/questions/{question_id}
            # Start from the context document and build the full path
            ref = db.collection("contexts").document(context_id)

            # Navigate through the path parts alternating between collection and document
            # Path parts: [proposed_questions, spd, questions, question_1]
            # We need: .collection(proposed_questions).document(spd).collection(questions).document(question_1)
            for i, part in enumerate(path_parts):
                if i % 2 == 0:
                    # Even index (0, 2, ...) = collection
                    ref = ref.collection(part)
                else:
                    # Odd index (1, 3, ...) = document
                    ref = ref.document(part)

            # The path has 4 parts, so the final ref should be a document
            # If path has odd number of parts, it would end on a collection (error)
            if len(path_parts) % 2 != 0:
                print(f"    ⚠️  Skipping invalid path (odd parts): {path}")
                continue

            try:
                ref.set(question_data)
                print(f"    ✅ {path}")
                total_questions += 1
            except Exception as e:
                print(f"    ❌ Failed to write {path}: {e}")
                failed_writes.append((context_id, path, str(e)))

    print(f"\nTotal proposed questions seeded: {total_questions}")

    if failed_files:
        print(f"\n⚠️  Failed to parse {len(failed_files)} file(s):")
        for filename, error in failed_files:
            print(f"    - {filename}: {error}")

    if failed_writes:
        print(f"\n⚠️  Failed to write {len(failed_writes)} document(s):")
        for context_id, path, error in failed_writes:
            print(f"    - {context_id}/{path}: {error}")

    return failed_files, failed_writes


def main():
    print("=" * 60)
    print("Firestore Seed Script")
    print("=" * 60)
    print(f"Environment: {ENV}")
    print(f"Data directory: {DATA_DIR}")

    if not DATA_DIR.exists():
        print(f"\n❌ Data directory not found: {DATA_DIR}")
        sys.exit(1)

    db = initialize_firebase()

    # Seed contexts first
    seed_contexts(db)

    # Seed parties for each context
    seed_parties(db)

    # Seed proposed questions for each context
    failed_files, failed_writes = seed_proposed_questions(db)

    if failed_files or failed_writes:
        print("\n" + "=" * 60)
        print(
            f"❌ Seeding FAILED: {len(failed_files)} unparseable file(s), "
            f"{len(failed_writes)} failed write(s)."
        )
        print("=" * 60)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ Seeding complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
