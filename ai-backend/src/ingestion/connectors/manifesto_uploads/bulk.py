# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Local CLI for the uploaded-manifesto connector.

Adds the checks and dry runs the generic runner cannot express, then delegates the
actual ingest to ``run_connector`` so there is ONE embed/upsert/reconcile
implementation (unlike the AW manifesto CLI, which predates that and carries its own
flush logic).

Usage (local dev):
    cd ai-backend
    uv run python -m src.ingestion.connectors.manifesto_uploads.bulk --check
    uv run python -m src.ingestion.connectors.manifesto_uploads.bulk --dry-run
    uv run python -m src.ingestion.connectors.manifesto_uploads.bulk --only spd,cdu
    QDRANT_URL=http://localhost:6333 ENV=dev uv run python -m src.ingestion.connectors.manifesto_uploads.bulk

``--check`` is the pre-ingest gate: it resolves every manifest entry against the
Firestore seed fixtures and reports what each document WOULD be stamped with, so a
wrong election/party/region is caught before anything is embedded rather than
surfacing later as a document the chat never cites.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date as date_type
from pathlib import Path
from typing import Optional

# CLI startup ONLY: load ai-backend/.env BEFORE the imports below — embeddings and
# setup_collection freeze EMBEDDING_MODEL / EMBEDDING_DIM / COLLECTION_NAME from the
# environment at import time, so a later load_dotenv() configures nothing.
# override=False keeps explicitly-exported shell env (ENV, QDRANT_URL) authoritative.
if __name__ == "__main__":
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[4] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

from src.ingestion.connectors.manifesto_uploads.connector import (
    ManifestoUploadsConnector,
    default_manifest_path,
    load_manifest,
    in_scope,
    load_pdf_pages,
    resolve_since_floor,
)
from src.ingestion.connectors.manifesto_uploads.election_fixtures import (
    FixtureLookupError,
    load_election,
    require_party,
)
from src.ingestion.connectors.manifesto_uploads.mappers.corpus import (
    build_citation_title,
)
from src.ingestion.connectors.manifesto_uploads.storage_paths import (
    UploadPathError,
    parse_object_path,
    staging_path,
)

logger = logging.getLogger(__name__)


def _party_of(object_path: str) -> str:
    """Party slug of an object path, lowercased ("" when unparseable)."""
    try:
        return parse_object_path(object_path).party_id.lower()
    except UploadPathError:
        return ""


def _filter_by_party(paths: list[str], only: Optional[set[str]]) -> list[str]:
    """Restrict *paths* to the given party slugs (``--only``)."""
    if not only:
        return paths
    return [path for path in paths if _party_of(path) in only]


def check(paths: list[str], env: Optional[str] = None) -> int:
    """Resolve every entry and print what it would be stamped with.

    Returns:
        Count of entries that failed to resolve (0 means the manifest is ingestable).
    """
    failures = 0
    for path in paths:
        try:
            ref = parse_object_path(path)
            fixture = load_election(ref.context_id, env)
            require_party(fixture, ref.party_id)
        except (UploadPathError, FixtureLookupError) as exc:
            print(f"  FAIL  {path}\n          {exc}")
            failures += 1
            continue

        staged = staging_path(path)
        where = "staged" if staged.exists() else "bucket only"
        print(
            f"  OK    {ref.party_id:17s} region={fixture.region:9s} "
            f"level={fixture.level:9s} publish={fixture.election_date} "
            f"doc={ref.document_date} [{where}]\n"
            f"          {build_citation_title(ref, fixture)}\n"
            f"          {ref.citation_url(env)}"
        )
    return failures


def dry_run(paths: list[str], env: Optional[str] = None) -> int:
    """Parse and chunk each document without embedding; print per-document stats.

    Returns:
        Count of documents that could not be read, parsed or chunked.
    """
    from src.ingestion.chunking import chunk_pages  # noqa: PLC0415

    failures = 0
    total_chunks = 0
    for path in paths:
        try:
            ref = parse_object_path(path)
            fixture = load_election(ref.context_id, env)
            require_party(fixture, ref.party_id)
            content = load_pdf_pages(path, env)
        except (UploadPathError, FixtureLookupError, ValueError) as exc:
            print(f"  FAIL  {path}\n          {exc}")
            failures += 1
            continue

        chunks = chunk_pages(content["pages"])
        chars = sum(len(text) for text, _s, _e in chunks)
        total_chunks += len(chunks)
        empty_pages = sum(1 for _no, text in content["pages"] if not text.strip())
        note = f"  ({empty_pages} page(s) with no text)" if empty_pages else ""
        print(
            f"  {ref.party_id:17s} pages={content['total_pages']:4d} "
            f"chars={chars:7d} chunks={len(chunks):4d}{note}"
        )
        if not chunks:
            print(
                "          WARNING: no text extracted — likely a scanned PDF (needs OCR)"
            )
            failures += 1
    print(f"\n  total chunks that would be embedded: {total_chunks}")
    return failures


def ingest(
    env: Optional[str] = None,
    only: Optional[set[str]] = None,
    since: Optional[date_type] = None,
    manifest_path: Optional[Path] = None,
) -> int:
    """Embed and upsert via the shared runner. Returns a process exit code.

    Note that the runner is driven over the connector's OWN discover() output, not
    over a pre-filtered path list: discover() adds the documents that are stored but
    no longer in the manifest, and those retirements must survive into the run —
    pinning the run to the manifest entries alone would silently disable cleanup.
    ``only`` narrows by PARTY, so a party's retirements are still processed.
    """
    import os  # noqa: PLC0415

    from qdrant_client import QdrantClient  # noqa: PLC0415

    from src.embeddings import get_embeddings  # noqa: PLC0415
    from src.ingestion.run import run_connector  # noqa: PLC0415
    from src.ingestion.setup_collection import (  # noqa: PLC0415
        COLLECTION_NAME,
        check_fingerprint,
    )

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )
    # Corpus passages → RETRIEVAL_DOCUMENT, pairing with RETRIEVAL_QUERY at query
    # time (no-op for OpenAI). Refuse a collection whose fingerprint contradicts
    # the configured embedding space.
    embed = get_embeddings(task_type="RETRIEVAL_DOCUMENT")
    check_fingerprint(qdrant, COLLECTION_NAME)

    connector = ManifestoUploadsConnector(
        manifest_path=manifest_path, env=env, since=since
    )
    if only:
        original_discover = connector.discover

        def discover_selected(since: Optional[int]) -> list[str]:
            return _filter_by_party(original_discover(since), only)

        connector.discover = discover_selected  # type: ignore[method-assign]

    report = run_connector(
        connector,
        qdrant,
        embed,
        COLLECTION_NAME,
        # The manifest holds tens of documents, not thousands, and every one of them
        # (plus any retirement) should be handled in a single run rather than
        # trickling over several — this is an operator-triggered command, not a
        # scheduled job working through a backlog.
        batch_size=1000,
    )
    print(
        f"\n=== uploaded manifestos ===\n"
        f"documents written      : {report.processed}\n"
        f"unchanged skips        : {report.present_skips}\n"
        f"chunks upserted        : {report.chunks_upserted}\n"
        f"failed                 : {len(report.failed_ids)}"
    )
    if report.failed_ids:
        print(f"failed documents       : {', '.join(report.failed_ids)}")
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description=(
            "Ingest party manifesto PDFs supplied directly to us (elections without "
            "Abgeordnetenwatch coverage) into the Qdrant wahlchat_chunks_{ENV} collection."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Resolve every manifest entry against the Firestore seed fixtures and "
            "print the region/party/date each document would be stamped with. "
            "No PDFs are read and nothing is written."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and chunk each PDF but skip embed + upsert; print per-document stats.",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        metavar="SLUG1,SLUG2",
        help="Restrict to these party slugs (e.g. --only spd,cdu).",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        metavar="PATH",
        help="Manifest file to use (default: data/manifesto_uploads/{ENV}.txt).",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "Only process documents whose ELECTION date is on or after this date "
            "(a chunk's publish_date IS its election date). Overrides "
            "MANIFESTO_UPLOADS_SINCE. Default: no floor. Use --since $(date +%%F) to "
            "restrict a bucket-wide run to elections that have not happened yet. "
            "Documents below the floor are neither ingested nor retired."
        ),
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        metavar="dev|prod",
        help="Seed-data environment and Storage bucket to target (default: $ENV, else dev).",
    )
    args = parser.parse_args()

    # An invalid floor is a loud misconfiguration, raised before any work.
    try:
        since_floor = resolve_since_floor(args.since)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    manifest_path = Path(args.manifest).expanduser() if args.manifest else None
    try:
        entries = load_manifest(manifest_path, args.env)
    except UploadPathError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not entries:
        print(
            f"No manifest entries found ({manifest_path or default_manifest_path(args.env)}).",
            file=sys.stderr,
        )
        sys.exit(1)

    # --check / --dry-run must show what would ACTUALLY be ingested, so the floor
    # applies to them too. (ingest() re-derives scope inside the connector, where
    # out-of-scope documents are also protected from retirement.)
    if since_floor is not None:
        in_window = [e for e in entries if in_scope(e, since_floor, args.env)]
        if len(in_window) != len(entries):
            print(
                f"{len(entries) - len(in_window)} document(s) below the "
                f"{since_floor} election-date floor — skipped\n"
            )
        entries = in_window
        if not entries:
            print(
                f"No documents with an election on or after {since_floor}.",
                file=sys.stderr,
            )
            sys.exit(1)

    only = (
        {slug.strip().lower() for slug in args.only.split(",") if slug.strip()}
        if args.only
        else None
    )
    entries = _filter_by_party(entries, only)
    if not entries:
        print(
            f"ERROR: --only {args.only!r} matched no manifest entries", file=sys.stderr
        )
        sys.exit(1)

    print(f"{len(entries)} document(s) selected\n")
    try:
        if args.check:
            sys.exit(1 if check(entries, args.env) else 0)
        if args.dry_run:
            sys.exit(1 if dry_run(entries, args.env) else 0)
        # A real ingest always validates first — embedding a mis-stamped document
        # wastes the embed cost and puts unreachable chunks in the corpus.
        if check(entries, args.env):
            print(
                "\nERROR: manifest did not validate — nothing was ingested.",
                file=sys.stderr,
            )
            sys.exit(1)
        print()
        sys.exit(ingest(args.env, only, since_floor, manifest_path))
    except Exception:  # noqa: BLE001
        import traceback  # noqa: PLC0415

        print("ERROR: run failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
