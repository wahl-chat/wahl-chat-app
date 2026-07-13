# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Generic run_connector() orchestrator for all wahl.chat V2 data source connectors.

A single synchronous fetch→normalize→embed→upsert pass.  The cursor (since) is
derived from Qdrant max(external_id) for the connector's source_type — no
Firestore, no GCS, no work queue.

Usage (local dev):
    uv run python -m src.ingestion.run --connector abgeordnetenwatch_votes

Usage (Cloud Run Job):
    ENV: CONNECTOR_ID=abgeordnetenwatch_votes

The runner is the same code path locally and in Cloud Run; the job spec sets
CONNECTOR_ID and the entrypoint is `python -m src.ingestion.run`.

Synchronous run loop:
    get_cursor(since) → discover(since) → per item:
      fetch → normalize (skip-and-warn on ValueError) → embed → upsert

Idempotent via deterministic Qdrant point IDs (compute_chunk_id).
Cursor auto-advances on the next run via get_cursor() scroll(DESC).
"""

import argparse
import difflib
import os
import re
import sys
import time
from typing import NamedTuple, Optional

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models
from tenacity import retry, stop_after_attempt, wait_exponential

from src.ingestion.connector import BaseConnector
from src.ingestion.schemas import ChunkRecord
from src.ingestion.setup_collection import (
    COLLECTION_NAME,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
)
from src.ingestion.ids import compute_chunk_id


# ---------------------------------------------------------------------------
# RunReport — lightweight result from a single run_connector() invocation.
# ---------------------------------------------------------------------------


class RunReport(NamedTuple):
    """Result of a single run_connector() call.

    Attributes:
        processed:        Number of items that DID WORK this run (embed+upsert of a
                          new item, or a content-changed/orphaned rewrite). Only
                          these consume the batch_size budget.
        remaining:        Estimated items remaining — the tail of discovered ids the
                          loop never reached (len(ids) - consumed).  This is an
                          estimate because discover() may return different results
                          on the next run.
        chunks_upserted:  Total number of ChunkRecord instances written to Qdrant
                          this run (sum of len(chunks) for each processed item that
                          produced non-empty chunks; skipped/empty items contribute 0).
        failed_ids:       External ids skipped this run due to a fetch/normalize/upsert
                          error. These are NOT lost — set-difference discovery re-surfaces
                          them next run — but they are surfaced here (and logged) so an
                          operator can see coverage gaps instead of them being swallowed.
        present_skips:    Items found already present AND unchanged AND orphan-free —
                          cheaply skipped (one footprint scroll, no embed) WITHOUT
                          consuming the batch_size budget, so an already-ingested
                          prefix of the discover() output can never stall the batch
                          window.
    """

    processed: int
    remaining: int
    chunks_upserted: int
    failed_ids: tuple[str, ...] = ()
    present_skips: int = 0


# ---------------------------------------------------------------------------
# get_cursor() — derive since from Qdrant max(external_id)
# ---------------------------------------------------------------------------


def get_cursor(
    qdrant: QdrantClient,
    collection_name: str,
    source_type: str,
    source: Optional[str] = None,
) -> Optional[int]:
    """Return max(external_id) for the given source_type from Qdrant, or None.

    Uses scroll(order_by=OrderBy(DESC), limit=1) — O(1) round-trip.
    Requires external_id IntegerIndexParams(range=True) index (setup_collection.py).

    When *source* is provided, a second FieldCondition(key="source") is appended to
    the scroll filter so connectors that share one source_type (op and DIP both use
    "parliamentary_speech") derive INDEPENDENT max(external_id) cursors instead of
    cross-pollinating one shared cursor (D-11/Q2). Connectors without a `source`
    attribute pass source=None → behaviour is byte-for-byte unchanged.

    Args:
        qdrant:          Initialised QdrantClient.
        collection_name: Qdrant collection to query.
        source_type:     Source type string (e.g. "vote_record") to scope the query.
        source:          Optional source string (e.g. "op" / "dip") to further scope
                         the cursor to one connector within a shared source_type.

    Returns:
        Max external_id integer, or None if no points exist for this source_type
        (and source, when supplied).
    """
    must = [
        models.FieldCondition(
            key="source_type",
            match=models.MatchValue(value=source_type),
        )
    ]
    if source is not None:
        must.append(
            models.FieldCondition(
                key="source",
                match=models.MatchValue(value=source),
            )
        )
    points, _ = qdrant.scroll(
        collection_name=collection_name,
        scroll_filter=models.Filter(must=must),
        order_by=models.OrderBy(
            key="external_id",
            direction=models.Direction.DESC,
        ),
        limit=1,
        with_payload=["external_id"],
        with_vectors=False,
    )
    if not points:
        return None
    # LOW-01: coerce to int only for an int or digit-string external_id; anything
    # else (missing / non-numeric / malformed) → None so the floor helpers treat
    # it as "no cursor" rather than letting a bad value under/over-shoot the run.
    val = points[0].payload.get("external_id")  # type: ignore[union-attr]
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str) and val.isdigit():
        return int(val)
    return None


# ---------------------------------------------------------------------------
# supersede_dip_duplicates() — op-gated post-upsert supersede-delete hook
# ---------------------------------------------------------------------------


# A DIP twin is superseded only when its normalized text matches the op speech
# this closely. The proceedings text is byte-identical in intent across op/DIP
# but ~99% identical in practice (op runs ~1% longer), and a DIFFERENT speech by
# the same speaker under the same agenda item scores far lower (~0.3–0.6), so
# this cleanly separates "same speech" from "distinct speech that merely shares
# the non-unique speech_key". See run's HIGH-1 fix.
_SUPERSEDE_TEXT_MATCH_RATIO = 0.85


def _norm_speech_text(text: Optional[str]) -> str:
    """Lowercase, alphanumeric-only fold for order-stable cross-source text compare."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def supersede_dip_duplicates(
    qdrant: QdrantClient,
    collection_name: str,
    op_chunks: list[ChunkRecord],
    *,
    connector: BaseConnector,
) -> int:
    """Merge the true DIP twin into an op speech, then delete ONLY that twin (D-04/D-09).

    NARROW, op-gated hook: fires ONLY when ``getattr(connector, "source", None) == "op"``.
    Called per just-upserted op item (all chunks of ONE op speech), so exactly one
    op speech is superseding here; the ambiguity is only ever on the DIP side.

    ``speech_key`` (``de-{ep}-{session}-{speaker}-{agenda}``) is NOT unique per
    speech and there is no exact shared op↔DIP id, so the old
    "delete every DIP row whose speech_key op just ingested" would delete a
    DISTINCT DIP speech that merely shares the key (a speaker's second turn under
    the same agenda item that op did NOT align) — a permanent grounding loss.
    Instead we identify the true twin by TEXT: the op speech carries the full
    proceedings text, so its genuine DIP twin is the same-key DIP speech whose
    normalized text matches (``ratio >= _SUPERSEDE_TEXT_MATCH_RATIO``). Distinct
    same-key DIP speeches score far lower and are left untouched.

    Per matched twin it then:
      1. **Grafts the transcript PDF** — copies the DIP twin's ``citation_url``
         (the plenary-protocol PDF) onto THIS op record (matched precisely on the
         op ``source_item_id``) as ``meta.transcript_pdf_url``, durably (wait=True)
         BEFORE the delete, so a crash can never lose the PDF with its source gone.
      2. **Deletes the DIP twin** by its ``source_item_id`` (all its chunks) —
         never by the shared, non-unique speech_key.

    Non-op / no-source connectors return 0 immediately (every other connector runs
    byte-for-byte unchanged). Returns the number of DIP twins superseded.

    Args:
        qdrant:          Initialised QdrantClient.
        collection_name: Target Qdrant collection.
        op_chunks:       The just-upserted op ChunkRecords (all chunks of one op
                         speech; may be several for a long speech).
        connector:       The connector being run — used only for the op source-gate.
    """
    if getattr(connector, "source", None) != "op":
        return 0

    # Group the just-upserted op chunks into distinct op speeches (by source_item_id),
    # each with its speech_key and full concatenated text.
    op_speeches: dict[str, dict] = {}
    for chunk in op_chunks:
        key = getattr(chunk, "speech_key", None)
        sid = getattr(chunk, "source_item_id", None)
        if key is None or sid is None:
            continue
        entry = op_speeches.setdefault(sid, {"key": key, "texts": []})
        entry["texts"].append(getattr(chunk, "text", "") or "")
    if not op_speeches:
        return 0

    keys = sorted({e["key"] for e in op_speeches.values()})

    # Collect DIP candidates under those keys, grouped into distinct DIP speeches
    # (by source_item_id) with their full text + protocol-PDF citation_url.
    dip_speeches: dict[str, dict] = {}
    next_offset = None
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="speech_key", match=models.MatchAny(any=keys)),
                    models.FieldCondition(key="source", match=models.MatchValue(value="dip")),
                ]
            ),
            with_payload=["speech_key", "source_item_id", "citation_url", "text"],
            with_vectors=False,
            limit=256,
            offset=next_offset,
        )
        for point in points:
            payload = point.payload or {}
            dsid = payload.get("source_item_id")
            if dsid is None:
                continue
            entry = dip_speeches.setdefault(
                dsid,
                {
                    "key": payload.get("speech_key"),
                    "texts": [],
                    "citation_url": payload.get("citation_url"),
                },
            )
            entry["texts"].append(payload.get("text") or "")
        if next_offset is None:
            break

    # Match each op speech to its true DIP twin by normalized-text similarity.
    graft_ops: list[tuple[str, str]] = []  # (op_source_item_id, pdf_url)
    delete_dip_sids: list[str] = []
    for op_sid, op in op_speeches.items():
        op_norm = _norm_speech_text(" ".join(op["texts"]))
        if not op_norm:
            continue
        for dsid, dip in dip_speeches.items():
            if dip["key"] != op["key"] or dsid in delete_dip_sids:
                continue
            dip_norm = _norm_speech_text(" ".join(dip["texts"]))
            if not dip_norm:
                continue
            ratio = difflib.SequenceMatcher(None, op_norm, dip_norm).ratio()
            if ratio >= _SUPERSEDE_TEXT_MATCH_RATIO:
                if dip["citation_url"]:
                    graft_ops.append((op_sid, dip["citation_url"]))
                delete_dip_sids.append(dsid)
                break  # one op speech has at most one DIP twin

    if not delete_dip_sids:
        return 0

    # 1. Graft each twin's transcript PDF onto its specific op record (by
    #    source_item_id, not the shared key), durably before the delete.
    if graft_ops:
        qdrant.batch_update_points(
            collection_name=collection_name,
            update_operations=[
                models.SetPayloadOperation(
                    set_payload=models.SetPayload(
                        payload={"transcript_pdf_url": pdf_url},
                        key="meta",
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="source_item_id",
                                    match=models.MatchValue(value=op_sid),
                                ),
                                models.FieldCondition(
                                    key="source", match=models.MatchValue(value="op")
                                ),
                            ]
                        ),
                    )
                )
                for op_sid, pdf_url in graft_ops
            ],
            wait=True,
        )

    # 2. Delete ONLY the matched DIP twins, by their source_item_id (all chunks).
    #    Distinct same-key DIP speeches op did not match are never touched.
    qdrant.delete(
        collection_name=collection_name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_item_id", match=models.MatchAny(any=delete_dip_sids)
                    ),
                    models.FieldCondition(key="source", match=models.MatchValue(value="dip")),
                ]
            )
        ),
        wait=True,
    )
    # T-11-11: operator visibility on the merge + duplicate deletion.
    print(
        f"supersede: grafted DIP transcript PDF onto {len(graft_ops)} op speech(es), "
        f"then deleted {len(delete_dip_sids)} matched DIP twin(s)",
        file=sys.stderr,
    )
    return len(delete_dip_sids)


# ---------------------------------------------------------------------------
# _embed_texts() — tenacity-wrapped embedding helper
# ---------------------------------------------------------------------------


@retry(
    wait=wait_exponential(multiplier=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _embed_texts(embed: OpenAIEmbeddings, texts: list[str]) -> list[list[float]]:
    """Embed a list of texts with bounded exponential backoff (tenacity).

    Retries up to 5 attempts: wait 1s → 2s → 4s → ... → max 30s.
    On final attempt the original exception is re-raised (reraise=True).
    """
    return embed.embed_documents(texts)


# ---------------------------------------------------------------------------
# _upsert_chunks() — dimension guard + Qdrant upsert
# ---------------------------------------------------------------------------


def _upsert_chunks(
    qdrant: QdrantClient,
    collection_name: str,
    chunks: list[ChunkRecord],
    vectors: list[list[float]],
) -> None:
    """Upsert ChunkRecord + vector pairs as PointStructs to Qdrant (idempotent).

    Asserts len(vector) == EMBEDDING_DIM before any upsert so dimension
    drift never reaches the index.  Raises ValueError on mismatch.

    Args:
        qdrant:          Initialised QdrantClient.
        collection_name: Target Qdrant collection.
        chunks:          ChunkRecord instances to upsert.
        vectors:         Corresponding embedding vectors (one per chunk).

    Raises:
        ValueError: If any vector's dimension != EMBEDDING_DIM.
    """
    from qdrant_client.models import PointStruct  # noqa: PLC0415

    points = []
    for chunk, vector in zip(chunks, vectors):
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"VEC-05: embedding dim mismatch: expected {EMBEDDING_DIM}, "
                f"got {len(vector)} for chunk {chunk.chunk_key!r}"
            )
        point_id = str(compute_chunk_id(chunk.source_item_id, chunk.chunk_index))
        points.append(
            PointStruct(
                id=point_id,
                vector={"dense": vector},
                payload=chunk.model_dump(mode="json", exclude_none=True),
            )
        )
    qdrant.upsert(collection_name=collection_name, points=points, wait=True)


# ---------------------------------------------------------------------------
# run_connector() — the generic synchronous orchestrator
# ---------------------------------------------------------------------------


def run_connector(
    connector: BaseConnector,
    qdrant: QdrantClient,
    embed: OpenAIEmbeddings,
    collection_name: str = COLLECTION_NAME,
    *,
    batch_size: int = 50,
    time_budget_s: Optional[float] = None,
) -> RunReport:
    """Drive *connector* through discover → fetch → normalize → embed → upsert.

    Cursor is derived from Qdrant max(external_id) for connector.source_type.
    No watermark write: cursor advances automatically on the next run via get_cursor().
    Safe-commit: if job dies mid-batch, re-discover + re-embed only the tail.
    Idempotent via deterministic point IDs (compute_chunk_id).

    Args:
        connector:       Any BaseConnector implementation.
        qdrant:          Initialised QdrantClient.
        embed:           Initialised OpenAIEmbeddings instance.
        collection_name: Qdrant collection to upsert into.
        batch_size:      Maximum number of items to process per run.
        time_budget_s:   Optional wall-clock budget in seconds.  If set and
                         exceeded mid-batch, the loop exits gracefully so the
                         next run re-processes the remaining items.

    Returns:
        RunReport(processed=N, remaining=M, chunks_upserted=C) where N is the
        number of items fully upserted this run, M is the estimated remaining
        count, and C is the total number of ChunkRecord instances written.
    """
    since = get_cursor(
        qdrant,
        collection_name,
        connector.source_type,  # type: ignore[attr-defined]
        source=getattr(connector, "source", None),
    )
    ids = connector.discover(since)

    started = time.monotonic()
    processed = 0
    present_skips = 0
    chunks_upserted = 0
    failed_ids: list[str] = []
    consumed = 0  # discovered ids the loop has reached (drives the remaining estimate)

    # Batch-window stall fix: iterate over ALL discovered ids (not a fixed
    # ids[:batch_size] slice) and only count an item toward the batch_size budget
    # when it actually DID WORK (embed+upsert or content-changed/orphaned rewrite).
    # Already-present-and-unchanged items are cheaply skipped (one footprint
    # scroll, no embed) and the loop continues past them, so a store whose first N
    # discovered ids are already present still reaches new items instead of
    # re-processing the same N forever.
    for external_id in ids:
        if processed >= batch_size:
            break
        consumed += 1
        did_work = False

        # Per-item resilience: wrap the ENTIRE per-item body (fetch →
        # normalize → already-present guard → embed → upsert) so that any Exception
        # from any step causes a skip-and-warn rather than aborting the whole run.
        # Timeouts are enforced at the client layer (AW: timeout=30, DIP: timeout=60).
        try:
            raw = connector.fetch(external_id)  # fetch timeouts enforced at client layer

            try:
                chunks = connector.normalize(raw)
            except ValueError as exc:
                # Keep the existing ValueError-specific normalize warning message wording.
                print(
                    f"WARNING: skipping item {external_id}: normalize failed: {exc}",
                    file=sys.stderr,
                )
                failed_ids.append(str(external_id))
                continue

            if chunks:
                # Already-present / orphan guard (cost optimisation + staleness fix):
                # Compute deterministic point IDs for this item's chunks (same formula as
                # _upsert_chunks) and compare against the FULL existing footprint of the
                # item's source_item_ids in Qdrant.
                #
                # normalize() output may span MANY source_item_ids (DIP/op emit one per
                # speech), so the footprint is collected per DISTINCT source_item_id via
                # a MatchAny scroll — a plain retrieve(ids=new_point_ids) would miss
                # stored points the new normalize no longer produces (orphans), letting
                # a 3→2 chunk shrink leave the stale 3rd chunk retrievable forever.
                #
                # The guard keys on point ID (source_item_id + chunk_index) AND, when the
                # connector stamps one, on content_hash — so an upstream CORRECTION that
                # reuses the same IDs but changes the content (e.g. a fixed AW vote tally,
                # surfaced by an AW_REFRESH reconcile run) is re-written rather than
                # silently skipped. Connectors that don't stamp content_hash keep plain
                # point-id-existence idempotency (content_changed stays False for them).
                point_ids = [
                    str(compute_chunk_id(c.source_item_id, c.chunk_index)) for c in chunks
                ]
                new_point_ids = set(point_ids)
                # source_item_id is a UUID; stringify for the keyword-index MatchAny.
                siids = sorted({str(c.source_item_id) for c in chunks})
                footprint_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_item_id",
                            match=models.MatchAny(any=siids),
                        )
                    ]
                )
                existing_hash_by_id: dict[str, Optional[str]] = {}
                next_offset = None
                while True:
                    points, next_offset = qdrant.scroll(
                        collection_name=collection_name,
                        scroll_filter=footprint_filter,
                        limit=1000,
                        offset=next_offset,
                        with_payload=["source_item_id", "content_hash"],
                        with_vectors=False,
                    )
                    for p in points:
                        existing_hash_by_id[str(p.id)] = (p.payload or {}).get(
                            "content_hash"
                        )
                    if next_offset is None:
                        break

                existing_point_ids = set(existing_hash_by_id.keys())
                all_present = new_point_ids.issubset(existing_point_ids)
                content_changed = any(
                    c.content_hash is not None
                    and existing_hash_by_id.get(pid) != c.content_hash
                    for pid, c in zip(point_ids, chunks)
                )
                # A stored point the new normalize no longer produces (e.g. a stale
                # higher-index chunk after a 3→2 shrink) — must be cleaned up even
                # when every NEW point id is present and unchanged.
                has_orphans = bool(existing_point_ids - new_point_ids)

                if (not all_present) or content_changed or has_orphans:
                    # Orphan cleanup: before upserting, delete ALL existing points
                    # across EVERY distinct source_item_id this item spans (one
                    # MatchAny filter) so orphans under every speech's siid are
                    # cleared — not just chunks[0]'s.
                    qdrant.delete(
                        collection_name=collection_name,
                        points_selector=models.FilterSelector(
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(
                                        key="source_item_id",
                                        match=models.MatchAny(any=siids),
                                    )
                                ]
                            )
                        ),
                        wait=True,
                    )
                    vectors = _embed_texts(embed, [c.text for c in chunks])
                    _upsert_chunks(qdrant, collection_name, chunks, vectors)
                    chunks_upserted += len(chunks)
                    # op-gated supersede hook (D-04/D-09): after a successful op
                    # upsert, delete the transient DIP duplicate(s) for each speech
                    # op just ingested. No-op for every non-op connector.
                    supersede_dip_duplicates(
                        qdrant,
                        collection_name,
                        chunks,
                        connector=connector,
                    )
                    did_work = True
                else:
                    # All chunks present AND content unchanged AND no orphans —
                    # cheap skip that does NOT consume the batch_size budget.
                    present_skips += 1

        except Exception as exc:  # noqa: BLE001
            # A dimension mismatch is a coding invariant, not a data error —
            # re-raise rather than silently skipping, so it is immediately visible.
            if "VEC-05" in str(exc):
                raise
            print(
                f"WARNING: skipping item {external_id}: unexpected error: {exc}",
                file=sys.stderr,
            )
            failed_ids.append(str(external_id))
            continue

        if did_work:
            processed += 1

        if time_budget_s is not None and time.monotonic() - started > time_budget_s:
            break

    # remaining is the not-yet-reached tail of discovered ids (ids after the last
    # index the loop consumed) — NOT len(ids) - processed, which would over-count
    # present-skips and failed items as "remaining".
    remaining = max(0, len(ids) - consumed)
    if failed_ids:
        print(
            f"WARNING: run_connector: {len(failed_ids)} item(s) skipped due to errors "
            f"and will be retried next run: {failed_ids}",
            file=sys.stderr,
        )
    return RunReport(
        processed=processed,
        remaining=remaining,
        chunks_upserted=chunks_upserted,
        failed_ids=tuple(failed_ids),
        present_skips=present_skips,
    )


# ---------------------------------------------------------------------------
# __main__ — CLI dispatch on CONNECTOR_ID / --connector arg
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Local-dev convenience: load ai-backend/.env if present so OPENAI_API_KEY
    # (and any other local secrets) are available for the embed step. This is
    # conditional on the file existing — Cloud Run Jobs have no .env, so env
    # there continues to come from the job spec (do NOT use utils.load_env(),
    # which hard-requires API_NAME and would crash the Cloud Run path).
    # override=False keeps any explicitly-exported env (e.g. CONNECTOR_ID) authoritative.
    from pathlib import Path  # noqa: PLC0415
    from dotenv import load_dotenv  # noqa: PLC0415

    _env_path = Path(__file__).resolve().parents[2] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

    # -----------------------------------------------------------------------
    # Parse connector_id from CONNECTOR_ID env or --connector arg.
    # -----------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="Run a wahl.chat V2 ingestion connector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Connector IDs: abgeordnetenwatch_votes, pledgetracker, manifestos, bundestag_speeches, openparliament_tv\n"
            "\n"
            "Local usage:\n"
            "  QDRANT_URL=http://localhost:6333 uv run python -m src.ingestion.run --connector abgeordnetenwatch_votes\n"
            "\n"
            "Cloud Run Job usage (D-03):\n"
            "  ENV: CONNECTOR_ID=abgeordnetenwatch_votes (set in job spec)\n"
        ),
    )
    parser.add_argument(
        "--connector",
        metavar="CONNECTOR_ID",
        help="Connector ID to run (overrides CONNECTOR_ID env var)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum items per run (default: 50)",
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Wall-clock time budget; gracefully exits mid-batch when exceeded",
    )
    args = parser.parse_args()

    # CONNECTOR_ID env takes precedence over --connector arg if both are set;
    # the arg is the local-dev convenience; the env is the Cloud Run path.
    connector_id = os.getenv("CONNECTOR_ID") or args.connector

    if not connector_id:
        print(
            "ERROR: No connector specified. "
            "Set CONNECTOR_ID env var or pass --connector <id>.",
            file=sys.stderr,
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Registry lookup — deferred import to avoid circular/missing-module errors
    # at startup.
    # -----------------------------------------------------------------------
    try:
        from src.ingestion import registry  # noqa: PLC0415

        factories = registry.CONNECTOR_FACTORIES
    except ImportError as exc:
        print(f"ERROR: Could not import registry: {exc}", file=sys.stderr)
        sys.exit(1)

    if connector_id not in factories:
        print(
            f"ERROR: Unknown connector '{connector_id}'. "
            f"Known IDs: {', '.join(sorted(factories))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Build Qdrant client and OpenAI embeddings, then run the connector.
    # -----------------------------------------------------------------------
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        _qdrant = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))
        _embed = OpenAIEmbeddings(model=EMBEDDING_MODEL)

        _connector = factories[connector_id]()

        _cursor_before = get_cursor(
            _qdrant,
            COLLECTION_NAME,
            _connector.source_type,
            source=getattr(_connector, "source", None),
        )

        _t0 = time.monotonic()
        _report = run_connector(
            _connector,
            _qdrant,
            _embed,
            batch_size=args.batch_size,
            time_budget_s=args.time_budget,
        )
        _duration = time.monotonic() - _t0

        _cursor_after = get_cursor(
            _qdrant,
            COLLECTION_NAME,
            _connector.source_type,
            source=getattr(_connector, "source", None),
        )

        print(
            f"run_connector({connector_id}): processed={_report.processed} remaining={_report.remaining}"
        )
        print(
            f"\n=== ingestion run: {connector_id} ===\n"
            f"cursor before : {_cursor_before}\n"
            f"cursor after  : {_cursor_after}\n"
            f"protocols/items processed : {_report.processed}\n"
            f"already-present skips : {_report.present_skips}\n"
            f"data points (chunks) upserted : {_report.chunks_upserted}\n"
            f"remaining (est.) : {_report.remaining}\n"
            f"duration : {_duration:.1f}s"
        )
    except Exception:  # noqa: BLE001
        # Emit the FULL traceback before exiting.
        import traceback  # noqa: PLC0415

        print("ERROR: connector run failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
