# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Local CLI for the uploaded-manifesto connector.

Adds --check/--dry-run, then delegates the actual ingest to ``run_connector`` — one
embed/upsert/reconcile implementation, unlike the AW manifesto CLI which predates it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date as date_type
from pathlib import Path
from typing import Optional

# CLI startup ONLY: load ingestion/.env BEFORE the imports below — embeddings and
# setup_collection freeze EMBEDDING_MODEL / EMBEDDING_DIM / COLLECTION_NAME from the
# environment at import time, so a later load_dotenv() configures nothing.
# override=False keeps explicitly-exported shell env (ENV, QDRANT_URL) authoritative.
if __name__ == "__main__":
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[4] / ".env"

    # Fall back to ai-backend/.env so setups that keep every key in one
    # file keep working after the ingestion split.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

from ingestion.connectors.manifesto_uploads.bucket_listing import (
    BucketListingError,
)
from ingestion.connectors.manifesto_uploads.connector import (
    ManifestoUploadsConnector,
    ManifestUnavailable,
    default_manifest_path,
    in_scope,
    load_pdf_pages,
    resolve_since_floor,
    work_list,
)
from ingestion.connectors.manifesto_uploads.election_fixtures import (
    FixtureLookupError,
    load_election,
    require_party,
)
from ingestion.connectors.manifesto_uploads.mappers.corpus import (
    UPLOAD_SOURCE,
    build_citation_title,
)
from ingestion.connectors.manifesto_uploads.storage_paths import (
    UploadPathError,
    parse_object_path,
    staging_path,
)
from ingestion.schemas import SourceType

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
            f"  OK    {ref.party_id:17s} {ref.document_type:15s} "
            f"region={fixture.region:9s} "
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
    from ingestion.chunking import chunk_pages  # noqa: PLC0415

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


def verify_reachable(qdrant, collection_name: str) -> list[str]:  # noqa: ANN001
    """Return the stored uploaded documents that vector search cannot reach.

    Stored-but-unreachable is invisible to every count-based check we have: the runner
    reports success, count() finds the chunks, the footprint scan agrees — and only an
    approximate search comes back empty. The collection disables the global HNSW graph
    (``m=0`` with tenant sub-indexes on ``party_id``), so a gap in one tenant's
    sub-index removes its chunks from retrieval with no error anywhere. That is how an
    uploaded 2026 Wahlprogramm can sit in the corpus while chat answers from a
    four-year-old Abgeordnetenwatch copy.

    Each document is probed with ONE OF ITS OWN stored vectors. A point that cannot
    retrieve itself is not reachable. No embedding call, and the result is deterministic
    rather than dependent on some probe question.

    The probe filter MUST mirror the shape chat actually queries with
    (``source_type`` + ``party_id`` + ``region``, see ``_retrieve_party_buckets``), not
    merely identify the document. An earlier version filtered ``party_id`` + ``source``
    — a combination nothing in the app uses — and reported every ``gruene`` upload as
    unreachable while chat retrieved them fine. Cause: with ``m=0`` the only navigable
    graph is the ``party_id`` tenant sub-graph, and ``source="upload"`` selects ~2% of
    that tenant, a slice whose filtered subgraph was unreachable from the entry point.
    Raising ``hnsw_ef`` did not help and ``exact=True`` scored 1.0, confirming the data
    was present and only the ANN path was blind. ``full_scan_threshold`` did not rescue
    it either: 1 415 matching points is far below the 10 000 threshold, but the planner
    weighs it against the selected tenant sub-index instead. So a filter shape no query
    uses can be silently unsearchable — probing with one is a false-alarm generator.
    """
    from qdrant_client import models as qdrant_models  # noqa: PLC0415

    scroll_filter = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="source_type",
                match=qdrant_models.MatchValue(value=SourceType.PARTY_MANIFESTO.value),
            ),
            qdrant_models.FieldCondition(
                key="source", match=qdrant_models.MatchValue(value=UPLOAD_SOURCE)
            ),
        ]
    )

    # One representative point per stored document, with its vector and the payload
    # fields the retrieval-shaped probe filter needs.
    probes: dict[str, tuple[str, str, list[float], object]] = {}
    next_offset = None
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=1000,
            offset=next_offset,
            with_payload=["meta.storage_object_path", "party_id", "region"],
            with_vectors=True,
        )
        for point in points:
            payload = point.payload or {}
            path = (payload.get("meta") or {}).get("storage_object_path")
            party_id = payload.get("party_id")
            region = payload.get("region")
            vector = (point.vector or {}).get("dense")
            if isinstance(path, str) and path and party_id and region and vector:
                probes.setdefault(path, (party_id, region, vector, point.id))
        if next_offset is None:
            break

    unreachable: list[str] = []
    for path, (party_id, region, vector, point_id) in sorted(probes.items()):
        hits = qdrant.query_points(
            collection_name=collection_name,
            query=vector,
            # Named vector — the collection has no unnamed default.
            using="dense",
            query_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="source_type",
                        match=qdrant_models.MatchValue(
                            value=SourceType.PARTY_MANIFESTO.value
                        ),
                    ),
                    qdrant_models.FieldCondition(
                        key="party_id",
                        match=qdrant_models.MatchValue(value=party_id),
                    ),
                    qdrant_models.FieldCondition(
                        key="region", match=qdrant_models.MatchValue(value=region)
                    ),
                ]
            ),
            # The filter now matches the party's whole manifesto set, AW copies
            # included, so "something came back" is not the assertion — the probe
            # point retrieving ITSELF is. Ask for a few and look for its own id,
            # otherwise an unreachable upload would pass on a reachable AW twin.
            limit=5,
        ).points
        if not any(hit.id == point_id for hit in hits):
            unreachable.append(path)
    return unreachable


def ingest(
    env: Optional[str] = None,
    only: Optional[set[str]] = None,
    since: Optional[date_type] = None,
    manifest_path: Optional[Path] = None,
) -> int:
    """Embed and upsert via the shared runner. Returns a process exit code.

    Runs over the connector's own discover() output, not a pre-filtered path list —
    that's what lets a document dropped from the manifest still get retired.
    """
    import os  # noqa: PLC0415

    from qdrant_client import QdrantClient  # noqa: PLC0415

    from wahlchat_common.embeddings import get_embeddings  # noqa: PLC0415
    from ingestion.run import run_connector  # noqa: PLC0415
    from ingestion.setup_collection import (  # noqa: PLC0415
        COLLECTION_NAME,
        check_fingerprint,
    )

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
        # qdrant-client defaults to httpx's 5s, which is ample against localhost and
        # far too short for a remote store: one upsert of a few hundred 3072-dim
        # vectors is multiple MB, and the client aborts mid-upload with "The write
        # operation timed out". Bandwidth-bound, so it fails the same documents every
        # run rather than looking flaky.
        timeout=int(os.getenv("QDRANT_TIMEOUT", "120")),
    )
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
        batch_size=1000,  # tens of documents, not thousands — handle all in one run
    )
    # Stored is not the same as retrievable — see verify_reachable. A flagged
    # document is re-checked once after a short pause, so ordinary optimizer lag
    # right after a write does not raise a false alarm.
    unreachable = verify_reachable(qdrant, COLLECTION_NAME)
    if unreachable:
        import time  # noqa: PLC0415

        time.sleep(5)
        unreachable = [
            p
            for p in verify_reachable(qdrant, COLLECTION_NAME)
            if p in set(unreachable)
        ]

    print(
        f"\n=== uploaded manifestos ===\n"
        f"documents written      : {report.processed}\n"
        f"unchanged skips        : {report.present_skips}\n"
        f"chunks upserted        : {report.chunks_upserted}\n"
        f"failed                 : {len(report.failed_ids)}\n"
        f"stored but unreachable : {len(unreachable)}"
    )
    if unreachable:
        print(
            "\nWARNING: these documents are stored but NOT retrievable — chat will "
            "silently fall back to other sources for them:",
            file=sys.stderr,
        )
        for path in unreachable:
            print(f"  {path}", file=sys.stderr)
        print(
            "Re-ingest them to rebuild their tenant sub-index, e.g.\n"
            '  make run-manifesto-uploads ARGS="--only <party>"\n'
            "after deleting their chunks; if it persists, the collection's m=0 "
            "vector-index config is the reason a missing sub-index is silent.",
            file=sys.stderr,
        )
    if report.failed_ids:
        print(f"failed documents       : {', '.join(report.failed_ids)}")
    return 1 if (report.failed_ids or unreachable) else 0


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
    read_only = args.check or args.dry_run

    # Preflight the work-list that will ACTUALLY be ingested, not the checked-in
    # manifest: under MANIFESTO_UPLOADS_SOURCE=bucket the connector re-discovers
    # from the bucket, so validating the manifest here would gate a different set
    # of documents — and would refuse to start at all for an ENV that ships no
    # manifest file.
    try:
        entries = work_list(manifest_path, args.env)
    except (
        UploadPathError,
        ManifestUnavailable,
        BucketListingError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not entries:
        print(
            f"Work-list is empty (manifest: {manifest_path or default_manifest_path(args.env)}; "
            "set MANIFESTO_UPLOADS_SOURCE=bucket to use the live bucket instead).",
            file=sys.stderr,
        )
        # An empty work-list is a valid complete desired state, so the ingest path
        # must still run — that is what retires uploads no longer wanted, including
        # the last one. Only the read-only modes have nothing left to show.
        if read_only:
            sys.exit(0)
        print(
            "Continuing: any uploaded manifesto still stored for an in-scope "
            "election will be RETIRED from the corpus.",
            file=sys.stderr,
        )

    # --check / --dry-run must show what would ACTUALLY be ingested, so the floor
    # applies to them too. (ingest() re-derives scope inside the connector, where
    # out-of-scope documents are also protected from retirement.)
    if since_floor is not None and entries:
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
            if read_only:
                sys.exit(0)

    only = (
        {slug.strip().lower() for slug in args.only.split(",") if slug.strip()}
        if args.only
        else None
    )
    if only:
        entries = _filter_by_party(entries, only)
        # An explicit --only that selects nothing is a user error, not a desired
        # state — never let it read as "retire everything".
        if not entries:
            print(
                f"ERROR: --only {args.only!r} matched no work-list entries",
                file=sys.stderr,
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
