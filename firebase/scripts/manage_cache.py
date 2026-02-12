#!/usr/bin/env python3
"""
Manage the cached_answers collection in Firestore.

The cache uses context-scoped paths:
    cached_answers/{context_id}/{party_id}/{cache_key}/{document_id}

Usage (from the firebase/ directory or via make targets):

    # Clear all cached answers
    python scripts/manage_cache.py clear

    # Clear cached answers for a specific context
    python scripts/manage_cache.py clear --context bundestagswahl-2025

    # Clear cached answers for a specific party within a context
    python scripts/manage_cache.py clear --context bundestagswahl-2025 --party spd

    # For production:
    ENV=prod python scripts/manage_cache.py clear
"""

import argparse
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

# Configuration
ENV = os.getenv("ENV", "dev")
SCRIPT_DIR = Path(__file__).parent
FIREBASE_DIR = SCRIPT_DIR.parent
REPO_ROOT = FIREBASE_DIR.parent

CREDENTIALS_FILE = (
    "wahl-chat-firebase-adminsdk.json"
    if ENV == "prod"
    else "wahl-chat-dev-firebase-adminsdk.json"
)

CACHED_ANSWERS_COLLECTION = "cached_answers"


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
        pass
    except Exception as e:
        print(f"⚠️  Could not validate credentials: {e}")


def initialize_firebase():
    """Initialize Firebase Admin SDK (reuses existing app if already initialized)."""
    try:
        app = firebase_admin.get_app()
        return firestore.client(app)
    except ValueError:
        pass

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


def _delete_collection_recursive(db, collection_ref, batch_size=100):
    """Recursively delete all documents in a collection and their sub-collections.

    Returns the number of documents deleted.
    """
    deleted = 0
    docs = list(collection_ref.limit(batch_size).stream())

    while docs:
        for doc in docs:
            # Recursively delete sub-collections first
            for sub_col in doc.reference.collections():
                deleted += _delete_collection_recursive(db, sub_col, batch_size)
            doc.reference.delete()
            deleted += 1

        docs = list(collection_ref.limit(batch_size).stream())

    return deleted


def clear_cache(db, context_id=None, party_id=None):
    """Clear cached answers from Firestore.

    Cache structure: cached_answers/{context_id}/{party_id}/{cache_key}/{document_id}

    Args:
        db: Firestore client
        context_id: If provided, only clear cache for this context.
        party_id: If provided (requires context_id), only clear cache for this party.
    """
    if party_id and not context_id:
        print("❌ --party requires --context to be specified as well.")
        sys.exit(1)

    if context_id and party_id:
        print(
            f"\n🗑️  Clearing cached answers for context '{context_id}', party '{party_id}'..."
        )
        target_ref = (
            db.collection(CACHED_ANSWERS_COLLECTION)
            .document(context_id)
            .collection(party_id)
        )
        deleted = _delete_collection_recursive(db, target_ref)
        # Also delete the party document itself if it exists
        party_doc = (
            db.collection(CACHED_ANSWERS_COLLECTION)
            .document(context_id)
            .collection(party_id)
        )
        print(f"  ✅ Deleted {deleted} cached answer documents")

    elif context_id:
        print(f"\n🗑️  Clearing all cached answers for context '{context_id}'...")
        context_doc_ref = db.collection(CACHED_ANSWERS_COLLECTION).document(context_id)

        # Delete all sub-collections (party IDs) under this context
        deleted = 0
        for party_col in context_doc_ref.collections():
            deleted += _delete_collection_recursive(db, party_col)

        print(f"  ✅ Deleted {deleted} cached answer documents")

    else:
        print("\n🗑️  Clearing ALL cached answers...")
        cache_ref = db.collection(CACHED_ANSWERS_COLLECTION)
        docs = list(cache_ref.stream())

        deleted = 0
        for doc in docs:
            # Each doc is a context_id document; delete its sub-collections
            for sub_col in doc.reference.collections():
                deleted += _delete_collection_recursive(db, sub_col)
            doc.reference.delete()
            deleted += 1

        # Also handle documents that may not have been returned yet
        if not docs:
            # If there are no context-level documents, there's nothing to clear
            print("  ℹ️  No cached answers found")
        else:
            print(
                f"  ✅ Deleted {deleted} cached answer documents (across all contexts)"
            )


def clear_legacy_cache(db):
    """Clear the old (pre-context-scoped) cached_answers collection.

    Old structure: cached_answers/{party_id}/{cache_key}/{document_id}

    This function is for migration only. It deletes any cached answers that
    follow the old path structure (where the first level is a party_id instead
    of a context_id).
    """
    print("\n🗑️  Clearing legacy (non-context-scoped) cached answers...")

    cache_ref = db.collection(CACHED_ANSWERS_COLLECTION)
    docs = list(cache_ref.stream())

    deleted = 0
    for doc in docs:
        for sub_col in doc.reference.collections():
            deleted += _delete_collection_recursive(db, sub_col)
        doc.reference.delete()
        deleted += 1

    if deleted:
        print(f"  ✅ Deleted {deleted} legacy cached answer documents")
    else:
        print("  ℹ️  No legacy cached answers found")


def main():
    parser = argparse.ArgumentParser(
        description="Manage the Firestore cached_answers collection."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear cached answers")
    clear_parser.add_argument(
        "--context",
        type=str,
        default=None,
        help="Only clear cache for this context_id (e.g., bundestagswahl-2025)",
    )
    clear_parser.add_argument(
        "--party",
        type=str,
        default=None,
        help="Only clear cache for this party_id (requires --context)",
    )

    # clear-legacy command
    subparsers.add_parser(
        "clear-legacy",
        help="Clear old non-context-scoped cached answers (migration helper)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    print("=" * 60)
    print("Cache Management")
    print("=" * 60)
    print(f"Environment: {ENV}")

    db = initialize_firebase()

    if args.command == "clear":
        clear_cache(db, context_id=args.context, party_id=args.party)
    elif args.command == "clear-legacy":
        clear_legacy_cache(db)

    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
