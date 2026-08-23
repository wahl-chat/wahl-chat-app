#!/usr/bin/env python3
"""
Seed Firestore with contexts, parties, and proposed questions data.

Usage (from the firebase/ directory):
    python scripts/seed_firestore.py

    # For production (also busts the live site's ISR cache):
    REVALIDATE_SECRET=... ENV=prod python scripts/seed_firestore.py

This script:
1. Imports all contexts from firestore_data/{env}/contexts.json
2. Imports parties from firestore_data/{env}/parties_{context_id}.json
   into contexts/{context_id}/parties sub-collection
3. Imports proposed questions from firestore_data/{env}/proposed_questions_{context_id}.json
   into contexts/{context_id}/proposed_questions sub-collection
4. Imports source documents from firestore_data/{env}/sources_{context_id}.json
   into sources/{context_id}/parties/{party_id}/source_documents

File naming convention:
- contexts.json: Contains all context documents
- parties_{context_id}.json: Contains parties for a specific context
  Example: parties_bundestagswahl-2025.json -> contexts/bundestagswahl-2025/parties/
- proposed_questions_{context_id}.json: Contains proposed questions for a specific context
  Example: proposed_questions_kommunalwahl-muenchen-2026.json
           -> contexts/kommunalwahl-muenchen-2026/proposed_questions/
- sources_{context_id}.json: Contains the source documents shown on the sources page
  Example: sources_landtagswahl-sachsen-anhalt-2026.json
           -> sources/landtagswahl-sachsen-anhalt-2026/parties/{party_id}/source_documents/
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

# Configuration
ENV = os.getenv("ENV", "dev")
SCRIPT_DIR = Path(__file__).parent
FIREBASE_DIR = SCRIPT_DIR.parent
REPO_ROOT = FIREBASE_DIR.parent
DATA_DIR = FIREBASE_DIR / "firestore_data" / ENV

# Service account JSON file (looked up in ai-backend/ where it's typically placed)
CREDENTIALS_FILE = (
    "wahl-chat-firebase-adminsdk.json"
    if ENV == "prod"
    else "wahl-chat-dev-firebase-adminsdk.json"
)


def _find_credentials_file():
    """Search for the service account JSON in common locations."""
    search_paths = [
        REPO_ROOT / "ai-backend" / CREDENTIALS_FILE,
        REPO_ROOT / CREDENTIALS_FILE,
        Path.cwd() / CREDENTIALS_FILE,
    ]
    for path in search_paths:
        if path.exists():
            return path
    return None


def _validate_adc():
    """Validate Application Default Credentials and give a clear error if expired."""
    try:
        import google.auth
        import google.auth.transport.requests
        from google.auth.exceptions import RefreshError

        adc_credentials, _ = google.auth.default()
        adc_credentials.refresh(google.auth.transport.requests.Request())
    except RefreshError:
        print(
            "\n"
            "============================================================\n"
            " Firebase credentials have expired.\n"
            " Run 'make auth' or 'gcloud auth application-default login'\n"
            " to re-authenticate.\n"
            "============================================================\n"
        )
        sys.exit(1)
    except ImportError:
        pass  # google.auth not installed; let firebase_admin handle it
    except Exception as e:
        print(f"⚠️  Could not validate credentials: {e}")


def _emulator_client():
    """Firestore client for the local emulator — no credentials involved.

    The emulator accepts any credential and verifies none, so requiring a real one
    would gate local seeding on cloud access the run never uses (an expired ADC login
    used to block `make seed-local` outright). Anonymous credentials are passed
    explicitly rather than letting the SDK fall through to ADC, which would still try
    to refresh that login.

    The project id must be explicit: the emulator serves each project as its own
    namespace, so inheriting a different one from gcloud config would seed a namespace
    the app never reads. `make seed-local` passes EMULATOR_PROJECT through.
    """
    from google.auth.credentials import AnonymousCredentials  # noqa: PLC0415
    from google.cloud import firestore as gcp_firestore  # noqa: PLC0415

    host = os.getenv("FIRESTORE_EMULATOR_HOST")
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not project:
        print(
            "\n"
            "============================================================\n"
            " FIRESTORE_EMULATOR_HOST is set but no project id is.\n"
            " Set GOOGLE_CLOUD_PROJECT to the project the emulator runs\n"
            " under (see EMULATOR_PROJECT in the Makefile), or use\n"
            " 'make seed-local', which passes it for you.\n"
            "============================================================\n"
        )
        sys.exit(1)

    print(f"Using the Firestore emulator at {host} (project {project}, no credentials)")
    return gcp_firestore.Client(
        project=project, credentials=AnonymousCredentials()
    )


def initialize_firebase():
    """Initialize Firestore — emulator, service account, or ADC, in that order."""
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        return _emulator_client()

    cred_path = _find_credentials_file()

    if cred_path:
        print(f"Using credentials: {cred_path}")
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
    else:
        print("Using Application Default Credentials (gcloud ADC)")
        _validate_adc()
        firebase_admin.initialize_app()

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


def seed_proposed_questions(db):
    """Seed proposed_questions sub-collections for each context.

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
        return

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


def seed_sources(db):
    """Seed source documents for each context's sources page.

    File structure: {party_id: {document_id: {name, storage_url, publish_date?}}}.
    Documents land at sources/{context_id}/parties/{party_id}/source_documents/{document_id},
    the path the web sources page reads. The storage-upload trigger writes the same shape
    (PartySource), but documents uploaded under the five-segment layout bypass it, so
    elections ingested via the ai-backend uploader are seeded from these files instead.
    publish_date is optional because external entries (abgeordnetenwatch.de etc.) have none.
    """
    sources_files = list(DATA_DIR.glob("sources_*.json"))

    if not sources_files:
        print("\n⚠️  No sources files found")
        return

    print(f"\n📁 Found {len(sources_files)} sources files")
    print("-" * 60)

    total_documents = 0
    for sources_file in sorted(sources_files):
        context_id = sources_file.stem.replace("sources_", "")

        with open(sources_file) as f:
            parties = json.load(f)

        print(f"\n  📂 {context_id} ({len(parties)} parties)")

        for party_id, documents in parties.items():
            for document_id, document in documents.items():
                data = dict(document)
                if "publish_date" in data:
                    data["publish_date"] = datetime.strptime(
                        data["publish_date"], "%Y-%m-%d"
                    ).replace(tzinfo=timezone.utc)
                (
                    db.collection("sources")
                    .document(context_id)
                    .collection("parties")
                    .document(party_id)
                    .collection("source_documents")
                    .document(document_id)
                    .set(data)
                )
                total_documents += 1
            print(f"    ✅ {party_id} ({len(documents)} documents)")

    print(f"\nTotal source documents seeded: {total_documents}")


# Tags the web app attaches to unstable_cache / ISR for the collections this
# script writes. A real-project seed that skips this leaves wahl.chat serving
# the previous hour's empty party list for a newly added context.
SEED_CACHE_TAGS = (
    "contexts",
    "context_parties",
    "proposed_questions",
    "source_documents",
)
DEFAULT_PROD_SITE_URL = "https://wahl.chat"


def _site_url():
    """Public origin of the Next.js app whose cache we must bust.

    REVALIDATE_URL / SITE_URL win; prod otherwise defaults to wahl.chat so a
    typical production seed only needs REVALIDATE_SECRET.
    """
    explicit = os.getenv("REVALIDATE_URL") or os.getenv("SITE_URL")
    if explicit:
        return explicit.rstrip("/")
    if ENV == "prod":
        return DEFAULT_PROD_SITE_URL
    return None


def _revalidate_payload(context_ids):
    paths = ["/"]
    for context_id in context_ids:
        paths.append(f"/{context_id}")
        paths.append(f"/{context_id}/sources")
    return {"tags": list(SEED_CACHE_TAGS), "paths": paths}


def revalidate_frontend_cache(context_ids):
    """Bust the live site's Firestore cache after a real-project seed.

    Local emulator reads skip Next's unstable_cache, so this is a no-op there.
    A cloud seed without REVALIDATE_SECRET (and a site URL, unless ENV=prod)
    exits: Firestore is already written, but the site will keep serving stale
    ISR until someone remembers to curl /api/revalidate.
    """
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        print("\nSkipping frontend cache revalidation (Firestore emulator).")
        return

    # REVALIDATE_SECRET is the web app's Vercel env var:
    # https://vercel.com/wahl-chat/web/settings/environment-variables
    secret = os.getenv("REVALIDATE_SECRET")
    site = _site_url()
    if not secret or not site:
        print(
            "\n"
            "============================================================\n"
            " Frontend cache was not revalidated.\n"
            " Set REVALIDATE_SECRET (same value as the web app) so the\n"
            " next seed busts ISR automatically. For a non-prod site also\n"
            " set SITE_URL or REVALIDATE_URL.\n"
            " Copy it from:\n"
            " https://vercel.com/wahl-chat/web/settings/environment-variables\n"
            "============================================================\n"
        )
        sys.exit(1)

    payload = _revalidate_payload(context_ids)
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
    print(f"\nRevalidating frontend cache at {url} ...")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        print(f"\n❌ Cache revalidation failed ({exc.code}): {detail}")
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"\n❌ Cache revalidation failed: {exc.reason}")
        sys.exit(1)

    print(
        f"  ✅ tags={payload['tags']} paths={len(payload['paths'])} ({body})"
    )


def main():
    print("=" * 60)
    print("Firestore Seed Script")
    print("=" * 60)
    print(f"Environment: {ENV}")
    print(f"Data directory: {DATA_DIR}")

    if not DATA_DIR.exists():
        print(f"\n❌ Data directory not found: {DATA_DIR}")
        return

    db = initialize_firebase()

    # Seed contexts first
    context_ids = seed_contexts(db)

    # Seed parties for each context
    seed_parties(db)

    # Seed proposed questions for each context
    seed_proposed_questions(db)

    # Seed source documents for each context's sources page
    seed_sources(db)

    revalidate_frontend_cache(context_ids)

    print("\n" + "=" * 60)
    print("✅ Seeding complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
