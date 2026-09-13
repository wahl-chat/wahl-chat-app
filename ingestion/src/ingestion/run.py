# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Generic run_connector() orchestrator for all wahl.chat data source connectors.

A single synchronous fetch→normalize→embed→upsert pass.  The cursor (since) is
derived from Qdrant max(external_id) for the connector's source_type — no
Firestore, no GCS, no work queue.

Usage (local dev):
    uv run python -m ingestion.run --connector abgeordnetenwatch_votes

Usage (Cloud Run Job):
    ENV: CONNECTOR_ID=abgeordnetenwatch_votes

The runner is the same code path locally and in Cloud Run; the job spec sets
CONNECTOR_ID and the entrypoint is `python -m ingestion.run`.

Synchronous run loop:
    get_cursor(since) → discover(since) → per item:
      fetch → normalize (skip-and-warn on ValueError) → embed → upsert

Idempotent via deterministic Qdrant point IDs (compute_chunk_id).
Cursor auto-advances on the next run via get_cursor() scroll(DESC).
"""

import argparse
import os
import sys
import time
from typing import NamedTuple, Optional

# CLI startup ONLY: load ingestion/.env BEFORE the imports below — embeddings
# and setup_collection freeze EMBEDDING_MODEL / EMBEDDING_DIM / COLLECTION_NAME
# from the environment at import time, so a load_dotenv() after them configures
# nothing (e.g. a Gemini .env would still run with the frozen OpenAI model
# name). Library imports (tests, other modules) are side-effect free — this
# block runs only under `python -m ingestion.run`. override=False keeps
# explicitly-exported env (e.g. CONNECTOR_ID, QDRANT_URL) authoritative;
# Cloud Run has no .env file, so the job-spec env passes through untouched.
if __name__ == "__main__":
    from pathlib import Path

    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[2] / ".env"

    # Fall back to ai-backend/.env so setups that keep every key in one
    # file keep working after the ingestion split.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient, models
from tenacity import retry, stop_after_attempt, wait_exponential

from wahlchat_common.embeddings import get_embeddings
from ingestion.connector import BaseConnector
from ingestion.schemas import ChunkRecord
from ingestion.setup_collection import (
    COLLECTION_NAME,
    EMBEDDING_DIM,
    check_fingerprint,
)
from ingestion.ids import compute_chunk_id


# ---------------------------------------------------------------------------
# DimensionMismatchError — embedding-dimension coding invariant
# ---------------------------------------------------------------------------


class DimensionMismatchError(ValueError):
    """Embedding vector dimension != EMBEDDING_DIM.

    A coding/config invariant violation, not a data error: run_connector
    re-raises it (isinstance check, not string matching) instead of
    skip-and-warning, so it is immediately visible. Subclasses ValueError to
    stay compatible with callers that catch ValueError.
    """


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
                          error. Whether they are re-surfaced next run depends on the
                          connector's discovery strategy (BaseConnector.discover):
                          set-difference discovery (AW, manifestos) re-surfaces every
                          failure; lookback-floor discovery (DIP, op) re-surfaces them
                          only while they remain inside the lookback window. Either way
                          they are surfaced here (and logged) so an operator can see
                          coverage gaps instead of them being swallowed.
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
    # Chunks whose party_id resolved to "unbekannt" among those upserted this
    # run. For the speech connectors this is the master-data drift signal: a
    # rising share means MdB-Stammdaten is stale or a speaker set went
    # unresolved. ~0 for connectors that always carry a real party_id.
    chunks_unbekannt: int = 0


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
    cross-pollinating one shared cursor. Connectors without a `source`
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
    # Coerce to int only for an int or digit-string external_id; anything
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
# _cursor_source_scope() — resolve the cursor's source scope for a connector
# ---------------------------------------------------------------------------


def _parent_key(connector: BaseConnector, external_id: str) -> str:
    """Stable per-parent identity for footprint reconciliation.

    Every chunk produced by ONE ``fetch(external_id)`` shares this key — the
    discover/fetch id IS the parent (a DIP protocol, an op session, an AW poll),
    even when ``normalize()`` fans it out into many ``source_item_id``s. Scoped by
    ``source_type`` + optional ``source`` (mirroring compute_source_item_id) so
    two connectors sharing a source_type but drawing from independent id spaces
    (dip/op) can never produce the same parent key for unrelated parents.
    """
    source = getattr(connector, "source", None)
    prefix = (
        f"{connector.source_type}:{source}" if source else str(connector.source_type)
    )
    return f"{prefix}:{external_id}"


def _cursor_source_scope(connector: BaseConnector) -> Optional[str]:
    """Return the source scope for get_cursor.

    ``connector.cursor_source`` when the attribute exists (BaseConnector
    defaults it to ``source``; subclasses may override — e.g. the DIP
    connector sets None so its floor spans both speech sources), else the
    plain ``source`` attribute (bare test stubs).
    """
    if hasattr(connector, "cursor_source"):
        return connector.cursor_source
    return getattr(connector, "source", None)


# ---------------------------------------------------------------------------
# _embed_texts() — tenacity-wrapped embedding helper
# ---------------------------------------------------------------------------


@retry(
    wait=wait_exponential(multiplier=1, max=30),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _embed_texts(embed: Embeddings, texts: list[str]) -> list[list[float]]:
    """Embed a list of texts with bounded exponential backoff (tenacity).

    Retries up to 5 attempts: wait 1s → 2s → 4s → ... → max 30s.
    On final attempt the original exception is re-raised (reraise=True).
    """
    return embed.embed_documents(texts)


# ---------------------------------------------------------------------------
# _upsert_chunks() — dimension guard + Qdrant upsert
# ---------------------------------------------------------------------------

# Points per upsert request. Qdrant rejects JSON request bodies over 32 MiB;
# a 3072-dim float vector serialises to ~60 KB, so a single very long source
# item (e.g. a plenary protocol with hundreds of chunks) can exceed the cap
# in one call. 256 points ≈ 16 MB worst case — half the limit.
_UPSERT_BATCH_POINTS = 256


def _upsert_chunks(
    qdrant: QdrantClient,
    collection_name: str,
    chunks: list[ChunkRecord],
    vectors: list[list[float]],
) -> None:
    """Upsert ChunkRecord + vector pairs as PointStructs to Qdrant (idempotent).

    Asserts len(vector) == EMBEDDING_DIM before any upsert so dimension
    drift never reaches the index.  Raises DimensionMismatchError on mismatch.

    Args:
        qdrant:          Initialised QdrantClient.
        collection_name: Target Qdrant collection.
        chunks:          ChunkRecord instances to upsert.
        vectors:         Corresponding embedding vectors (one per chunk).

    Raises:
        DimensionMismatchError: If any vector's dimension != EMBEDDING_DIM.
    """
    from qdrant_client.models import PointStruct  # noqa: PLC0415

    if len(vectors) != len(chunks):
        # A provider returning the wrong number of vectors is a coding/config
        # invariant violation; a plain zip would silently drop the tail chunks.
        raise DimensionMismatchError(
            f"embedding count mismatch: {len(chunks)} chunks but {len(vectors)} vectors"
        )
    points = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != EMBEDDING_DIM:
            raise DimensionMismatchError(
                f"embedding dim mismatch: expected {EMBEDDING_DIM}, "
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
    # Sliced so one oversized item cannot exceed Qdrant's request-size cap.
    # Deterministic point IDs keep a partially-applied item idempotent: the
    # next run re-embeds and overwrites the same points.
    for start in range(0, len(points), _UPSERT_BATCH_POINTS):
        qdrant.upsert(
            collection_name=collection_name,
            points=points[start : start + _UPSERT_BATCH_POINTS],
            wait=True,
        )


# ---------------------------------------------------------------------------
# Per-item helpers for run_connector() — each stage of the reconcile-and-write
# decision is its own function so the orchestrator reads as a flat sequence.
# ---------------------------------------------------------------------------


def _delete_superseded_twins(
    qdrant: QdrantClient, collection_name: str, connector: BaseConnector
) -> None:
    """Delete stored points for source_item_ids the connector reports superseded.

    Concurrent DIP+op hazard: a connector may report the source_item_ids its
    normalize() SKIPPED as already-superseded (the DIP connector sets
    last_superseded_siids). Any stored points under those siids are stranded
    twins from an interleaved concurrent run — they appear in NO new-chunk or
    orphan filter, so they are deleted here. No-op for every connector that
    does not expose the attribute.
    """
    superseded_siids = [
        str(s) for s in (getattr(connector, "last_superseded_siids", ()) or ())
    ]
    if not superseded_siids:
        return
    qdrant.delete(
        collection_name=collection_name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_item_id",
                        match=models.MatchAny(any=superseded_siids),
                    )
                ]
            )
        ),
        wait=True,
    )


def _scan_parent_footprint(
    qdrant: QdrantClient,
    collection_name: str,
    siids: list[str],
    parent_key: str,
) -> tuple[dict[str, Optional[str]], dict[str, str]]:
    """Scroll the parent's FULL stored footprint.

    Two scopes, unioned:
      1. source_item_id — the children the NEW normalize emits (also finds
         points written before source_parent_key existed, on the transition
         run before the corpus is re-ingested). Skipped when *siids* is empty.
      2. source_parent_key — the stable per-parent identity, so a child the
         new normalize no longer emits at all (a protocol that produced
         speeches A+B now producing only A, or nothing) is still scanned and
         reconciled. A source_item_id-only scope can only see children the new
         output names, so it would leave a wholly-disappeared child
         retrievable forever.

    Returns:
        (existing_hash_by_id, pdf_by_siid) where existing_hash_by_id maps each
        stored point id to its content_hash (None when the point carries none)
        and pdf_by_siid maps source_item_id → grafted DIP transcript PDF URL
        (meta.transcript_pdf_url, written by the op supersede pass) — the
        graft must survive a rewrite, since fresh mapper output never carries
        it and the DIP twin that donated it is already deleted.
    """
    existing_hash_by_id: dict[str, Optional[str]] = {}
    pdf_by_siid: dict[str, str] = {}
    footprint_scopes: list[models.FieldCondition] = []
    if siids:
        footprint_scopes.append(
            models.FieldCondition(
                key="source_item_id", match=models.MatchAny(any=siids)
            )
        )
    footprint_scopes.append(
        models.FieldCondition(
            key="source_parent_key", match=models.MatchValue(value=parent_key)
        )
    )
    for scope in footprint_scopes:
        scope_filter = models.Filter(must=[scope])
        next_offset = None
        while True:
            points, next_offset = qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=scope_filter,
                limit=1000,
                offset=next_offset,
                with_payload=[
                    "source_item_id",
                    "content_hash",
                    "meta.transcript_pdf_url",
                ],
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                existing_hash_by_id[str(p.id)] = payload.get("content_hash")
                grafted_pdf = (payload.get("meta") or {}).get("transcript_pdf_url")
                if grafted_pdf and payload.get("source_item_id") is not None:
                    pdf_by_siid.setdefault(str(payload["source_item_id"]), grafted_pdf)
            if next_offset is None:
                break
    return existing_hash_by_id, pdf_by_siid


def _reapply_grafted_pdfs(
    chunks: list[ChunkRecord], pdf_by_siid: dict[str, str]
) -> list[ChunkRecord]:
    """Re-apply grafted transcript PDFs to fresh mapper output.

    Only where the fresh output lacks one, so an op re-write cannot strip the
    supersede merge result. content_hash is computed by the mapper BEFORE this
    graft, so idempotency comparisons on later runs are unaffected.
    """
    if not pdf_by_siid:
        return chunks
    return [
        c.model_copy(
            update={
                "meta": {
                    **(c.meta or {}),
                    "transcript_pdf_url": pdf_by_siid[str(c.source_item_id)],
                }
            }
        )
        if str(c.source_item_id) in pdf_by_siid
        and "transcript_pdf_url" not in (c.meta or {})
        else c
        for c in chunks
    ]


# ---------------------------------------------------------------------------
# run_connector() — the generic synchronous orchestrator
# ---------------------------------------------------------------------------


def run_connector(
    connector: BaseConnector,
    qdrant: QdrantClient,
    embed: Embeddings,
    collection_name: str = COLLECTION_NAME,
    *,
    batch_size: int = 50,
    time_budget_s: Optional[float] = None,
    since_override: Optional[int] = None,
) -> RunReport:
    """Drive *connector* through discover → fetch → normalize → embed → upsert.

    Cursor is derived from Qdrant max(external_id) for connector.source_type.
    No watermark write: cursor advances automatically on the next run via get_cursor().
    Safe-commit: if job dies mid-batch, re-discover + re-embed only the tail.
    Idempotent via deterministic point IDs (compute_chunk_id).

    Args:
        connector:       Any BaseConnector implementation.
        qdrant:          Initialised QdrantClient.
        embed:           Initialised embeddings client (from get_embeddings()).
        collection_name: Qdrant collection to upsert into.
        batch_size:      Maximum number of items to process per run.
        time_budget_s:   Optional wall-clock budget in seconds.  If set and
                         exceeded mid-batch, the loop exits gracefully so the
                         next run re-processes the remaining items.
        since_override:  Explicit cursor value passed to discover() instead of
                         the Qdrant-derived max(external_id). The derived cursor
                         only moves forward, so items below it are never
                         re-discovered; an operator backfilling a window the
                         cursor has already passed (e.g. an older Wahlperiode
                         after a newer one advanced a shared cursor) supplies
                         the window start here. Already-present items inside
                         the window are content-hash skips — cheap, no re-embed.

    Returns:
        RunReport(processed=N, remaining=M, chunks_upserted=C) where N is the
        number of items fully upserted this run, M is the estimated remaining
        count, and C is the total number of ChunkRecord instances written.
    """
    # Refuse to write into a collection whose stored embedding-space
    # fingerprint contradicts the current configuration (soft-pass when the
    # store predates fingerprints or the client cannot read points).
    check_fingerprint(qdrant, collection_name)

    # One run, one store contract: store-aware discovery must read the same
    # client/collection this runner upserts into. hasattr-guarded so bare test
    # stubs that don't subclass BaseConnector keep working.
    if hasattr(connector, "bind_store"):
        connector.bind_store(qdrant, collection_name)

    since = (
        since_override
        if since_override is not None
        else get_cursor(
            qdrant,
            collection_name,
            connector.source_type,
            source=_cursor_source_scope(connector),
        )
    )
    ids = connector.discover(since)

    started = time.monotonic()
    processed = 0
    present_skips = 0
    chunks_upserted = 0
    chunks_unbekannt = 0
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
            raw = connector.fetch(
                external_id
            )  # fetch timeouts enforced at client layer

            try:
                chunks = connector.normalize(raw)
            except ValueError as exc:
                print(
                    f"WARNING: skipping item {external_id}: normalize failed: {exc}",
                    file=sys.stderr,
                )
                failed_ids.append(str(external_id))
                continue

            # Stamp the stable per-parent key (the discover/fetch id, source-scoped)
            # onto every chunk so the footprint scan can reconcile EVERY child
            # this parent ever produced — including a source_item_id this normalize()
            # no longer emits. content_hash is computed by the mapper BEFORE this stamp,
            # so idempotency comparisons on later runs are unaffected.
            parent_key = _parent_key(connector, str(external_id))
            chunks = [
                c.model_copy(update={"source_parent_key": parent_key}) for c in chunks
            ]

            _delete_superseded_twins(qdrant, collection_name, connector)

            # source_item_id is a UUID; stringify for the keyword-index MatchAny.
            siids = sorted({str(c.source_item_id) for c in chunks})
            existing_hash_by_id, pdf_by_siid = _scan_parent_footprint(
                qdrant, collection_name, siids, parent_key
            )
            existing_point_ids = set(existing_hash_by_id.keys())

            if not chunks:
                # Authoritative empty result: normalize() SUCCEEDED with zero
                # chunks (failures raise and are skip-and-warned above), so the
                # parent's footprint is now empty. Delete whatever it produced
                # before — otherwise a parent that shrinks to nothing keeps its
                # old chunks retrievable forever.
                if existing_point_ids:
                    qdrant.delete(
                        collection_name=collection_name,
                        points_selector=models.PointIdsList(
                            points=sorted(existing_point_ids)
                        ),
                        wait=True,
                    )
                    did_work = True
                else:
                    present_skips += 1
            else:
                # Already-present / orphan guard (cost optimisation + staleness
                # fix): compare deterministic point IDs (same formula as
                # _upsert_chunks) against the parent's full stored footprint.
                #
                # The guard keys on point ID (source_item_id + chunk_index) AND,
                # when the connector stamps one, on content_hash — so an upstream
                # CORRECTION that reuses the same IDs but changes the content
                # (e.g. a fixed AW vote tally, surfaced by an AW_REFRESH reconcile
                # run) is re-written rather than silently skipped. Connectors that
                # don't stamp content_hash keep plain point-id-existence
                # idempotency (content_changed stays False for them).
                point_ids = [
                    str(compute_chunk_id(c.source_item_id, c.chunk_index))
                    for c in chunks
                ]
                new_point_ids = set(point_ids)
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
                    # Loss-window fix — order matters:
                    #   1. EMBED first: the external call (5 tenacity retries) is
                    #      the failure-prone step. The old delete-before-embed
                    #      left the item ABSENT from the store when the embed
                    #      failed in between; connectors whose discovery cannot
                    #      re-surface it past the lookback window lost it forever.
                    #   2. Delete ONLY the orphan point ids (stored points the new
                    #      normalize no longer produces) — the surviving ids are
                    #      overwritten in place by the idempotent upsert, so the
                    #      item is never absent at any point in time.
                    #   3. Upsert (wait=True inside _upsert_chunks).
                    vectors = _embed_texts(embed, [c.text for c in chunks])
                    chunks = _reapply_grafted_pdfs(chunks, pdf_by_siid)
                    orphan_ids = sorted(existing_point_ids - new_point_ids)
                    if orphan_ids:
                        qdrant.delete(
                            collection_name=collection_name,
                            points_selector=models.PointIdsList(points=orphan_ids),
                            wait=True,
                        )
                    _upsert_chunks(qdrant, collection_name, chunks, vectors)
                    chunks_upserted += len(chunks)
                    chunks_unbekannt += sum(
                        1 for c in chunks if getattr(c, "party_id", None) == "unbekannt"
                    )
                    # Post-upsert connector hook: source-specific follow-up
                    # policy (e.g. the op connector's supersede-the-DIP-twin merge)
                    # lives on the connector, not in this generic runner. The
                    # BaseConnector default is a no-op returning 0.
                    connector.post_upsert(qdrant, collection_name, chunks)
                    did_work = True
                else:
                    # All chunks present AND content unchanged AND no orphans —
                    # cheap skip that does NOT consume the batch_size budget.
                    present_skips += 1

        except DimensionMismatchError:
            # A dimension mismatch is a coding invariant, not a data error —
            # re-raise (typed, not substring-matched) rather than silently
            # skipping, so it is immediately visible.
            raise
        except Exception as exc:  # noqa: BLE001
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
        chunks_unbekannt=chunks_unbekannt,
    )


# ---------------------------------------------------------------------------
# __main__ — CLI dispatch on CONNECTOR_ID / --connector arg
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    # This CLI block is the PRODUCTION entrypoint (the Cloud Run Job runs
    # `python -m ingestion.run` with CONNECTOR_ID in the job spec) — the
    # only local-dev convenience is the .env loading at the top of the module
    # (which must run before configuration imports freeze env-derived
    # constants; Cloud Run has no .env, so its job-spec env passes through).

    # -----------------------------------------------------------------------
    # Parse connector_id from CONNECTOR_ID env or --connector arg.
    # -----------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="Run a wahl.chat ingestion connector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Connector IDs: abgeordnetenwatch_votes, manifestos, bundestag_speeches, openparliament_tv\n"
            "\n"
            "A comma-separated value runs connectors sequentially in one process,\n"
            "in order. The speech pair MUST be run this way so they never overlap:\n"
            "  --connector bundestag_speeches,openparliament_tv\n"
            "\n"
            "Local usage:\n"
            "  QDRANT_URL=http://localhost:6333 uv run python -m ingestion.run --connector abgeordnetenwatch_votes\n"
            "\n"
            "Cloud Run Job usage:\n"
            "  CONNECTOR_ID=abgeordnetenwatch_votes (set in job spec)\n"
        ),
    )
    parser.add_argument(
        "--connector",
        metavar="CONNECTOR_ID[,CONNECTOR_ID...]",
        help="Connector ID(s) to run, comma-separated for a sequential run "
        "(overrides CONNECTOR_ID env var)",
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
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        metavar="EXTERNAL_ID",
        help=(
            "Override the Qdrant-derived cursor with an explicit external_id "
            "floor (connector-specific format, e.g. YYYYMMDD for speeches). "
            "Use to backfill a window the auto-advancing cursor has already "
            "passed; already-present items are skipped without re-embedding. "
            "Default: derive from the store."
        ),
    )
    args = parser.parse_args()

    # An explicit --connector arg wins over the CONNECTOR_ID env (matches the
    # argparse help text): the arg is the operator's deliberate local choice;
    # the env is the Cloud Run job-spec path — and run.py loads .env above, so
    # a stray CONNECTOR_ID= line must never override an explicit CLI arg.
    raw_connectors = args.connector or os.getenv("CONNECTOR_ID")

    if not raw_connectors:
        print(
            "ERROR: No connector specified. "
            "Set CONNECTOR_ID env var or pass --connector <id>.",
            file=sys.stderr,
        )
        sys.exit(1)

    # A comma-separated value runs several connectors SEQUENTIALLY in one
    # process, in the given order. This is how the coupled speech pair is
    # scheduled — "bundestag_speeches,openparliament_tv" runs DIP then op
    # back-to-back — making their must-never-overlap invariant structural
    # (see openparliament_tv/supersede.py) instead of a scheduler concern.
    connector_ids = [c.strip() for c in raw_connectors.split(",") if c.strip()]

    # -----------------------------------------------------------------------
    # Registry lookup — deferred import to avoid circular/missing-module errors
    # at startup.
    # -----------------------------------------------------------------------
    try:
        from ingestion import registry  # noqa: PLC0415

        factories = registry.CONNECTOR_FACTORIES
    except ImportError as exc:
        print(f"ERROR: Could not import registry: {exc}", file=sys.stderr)
        sys.exit(1)

    unknown = [cid for cid in connector_ids if cid not in factories]
    if unknown:
        print(
            f"ERROR: Unknown connector(s): {', '.join(unknown)}. "
            f"Known IDs: {', '.join(sorted(factories))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Build Qdrant client and OpenAI embeddings ONCE, shared across the
    # sequential connector runs; then run each connector in order. A failure in
    # any connector aborts the job (loud); already-committed work is idempotent,
    # so the next run safely re-processes only the tail.
    # -----------------------------------------------------------------------
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        # See bulk.py: the 5s httpx default aborts multi-MB upserts to a remote store.
        _qdrant = QdrantClient(
            url=qdrant_url,
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=int(os.getenv("QDRANT_TIMEOUT", "120")),
        )
        # Corpus passages → RETRIEVAL_DOCUMENT (Gemini asymmetric doc/query space;
        # ignored for OpenAI). Must match the RETRIEVAL_QUERY side in retrieve.py.
        _embed = get_embeddings(task_type="RETRIEVAL_DOCUMENT")

        for connector_id in connector_ids:
            _connector = factories[connector_id]()

            _cursor_before = get_cursor(
                _qdrant,
                COLLECTION_NAME,
                _connector.source_type,
                source=_cursor_source_scope(_connector),
            )

            _t0 = time.monotonic()
            _report = run_connector(
                _connector,
                _qdrant,
                _embed,
                batch_size=args.batch_size,
                time_budget_s=args.time_budget,
                since_override=args.since,
            )
            _duration = time.monotonic() - _t0

            _cursor_after = get_cursor(
                _qdrant,
                COLLECTION_NAME,
                _connector.source_type,
                source=_cursor_source_scope(_connector),
            )

            # Master-data drift signal: share of upserted chunks whose party
            # stayed "unbekannt". Meaningful for the speech connectors; ~0 for
            # connectors that always carry a real party_id.
            _unbekannt_pct = (
                f"{_report.chunks_unbekannt / _report.chunks_upserted:.1%}"
                if _report.chunks_upserted
                else "n/a"
            )

            print(
                f"\n=== ingestion run: {connector_id} ===\n"
                f"cursor before : {_cursor_before}\n"
                f"cursor after  : {_cursor_after}\n"
                f"protocols/items processed : {_report.processed}\n"
                f"already-present skips : {_report.present_skips}\n"
                f"data points (chunks) upserted : {_report.chunks_upserted}\n"
                f"unresolved party (unbekannt) chunks : {_report.chunks_unbekannt} ({_unbekannt_pct})\n"
                f"remaining (est.) : {_report.remaining}\n"
                f"duration : {_duration:.1f}s"
            )
    except Exception:  # noqa: BLE001
        # Emit the FULL traceback before exiting.
        import traceback  # noqa: PLC0415

        print("ERROR: connector run failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
