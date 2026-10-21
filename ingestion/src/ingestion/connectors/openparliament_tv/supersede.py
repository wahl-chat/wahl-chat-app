# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
op→DIP supersede policy — owned by the openparliament_tv connector.

Relocated from the generic runner (run.py): the "op supersedes its DIP twin"
merge is source-specific policy, not framework behavior. The runner now exposes
a neutral ``BaseConnector.post_upsert`` hook; ``OpenParliamentTvConnector``
implements it by calling :func:`supersede_dip_duplicates` for each just-upserted
op item. Every other connector inherits the no-op hook.

CONCURRENCY HAZARD: the DIP (bundestag_speeches) and op schedules MUST be
serialized — never run both connectors concurrently. Interleaving
"DIP resurrection-guard passes → op ingests+supersedes → DIP commits" strands a
DIP twin whose source_item_id never appears in either connector's later
new-chunk/orphan filters (op present-skips the session; DIP present-skips the
protocol). Mitigation implemented in addition to this doctrine: the DIP
connector's normalize() reports the siids it SKIPPED as op-superseded
(``last_superseded_siids``) and run_connector deletes any stored points under
them, so a stranded twin self-heals on the next serialized DIP run.
"""

from __future__ import annotations

import difflib
import sys

from qdrant_client import QdrantClient, models

from ingestion.connector import BaseConnector
from ingestion.schemas import ChunkRecord

# Shared with the DIP resurrection guard: a DIP twin is superseded only
# when its normalized text matches the op speech at/above this ratio — see the
# rationale in ingestion/src/ingestion/speech_dedup.py.
from ingestion.speech_dedup import (
    SUPERSEDE_TEXT_MATCH_RATIO as _SUPERSEDE_TEXT_MATCH_RATIO,
)
from ingestion.speech_dedup import norm_speech_text as _norm_speech_text


def _join_indexed_texts(texts: list[tuple[int, str]]) -> str:
    """Join (chunk_index, text) pairs in chunk_index order.

    A 2+-chunk speech scrolled out of order would otherwise concatenate as
    "B+A" and SequenceMatcher("A+B", "B+A") ≈ 0.5 < 0.85 — a silent supersede
    miss followed by a resurrection-guard re-insert.
    """
    return " ".join(t for _idx, t in sorted(texts, key=lambda pair: pair[0]))


def supersede_dip_duplicates(
    qdrant: QdrantClient,
    collection_name: str,
    op_chunks: list[ChunkRecord],
    *,
    connector: BaseConnector,
) -> int:
    """Merge the true DIP twin into an op speech, then delete ONLY that twin.

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
    # ChunkRecord.source_item_id is a uuid.UUID — key by str(sid) consistently so the
    # downstream MatchValue graft filter (which accepts only bool/int/str) never
    # receives a raw UUID (that ValidationError silently disabled the merge forever:
    # the per-item except fired AFTER the upsert, so the next run present-skipped).
    op_speeches: dict[str, dict] = {}
    for chunk in op_chunks:
        # op_chunks are real ChunkRecord instances; every field below is declared
        # on the model, so plain attribute access is correct (getattr would only
        # imply a dict-like path that does not exist here).
        key = chunk.speech_key
        sid = chunk.source_item_id
        if key is None or sid is None:
            continue
        entry = op_speeches.setdefault(str(sid), {"key": key, "texts": []})
        entry["texts"].append((chunk.chunk_index or 0, chunk.text or ""))
    if not op_speeches:
        return 0

    keys = sorted({e["key"] for e in op_speeches.values()})

    # Collect DIP candidates under those keys, grouped into distinct DIP speeches
    # (by source_item_id, stringified — stored payloads serialize it to str) with
    # their (chunk_index, text) pairs + protocol-PDF citation_url. chunk_index is
    # fetched so a multi-chunk speech joins in chunk order, not scroll order.
    dip_speeches: dict[str, dict] = {}
    next_offset = None
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="speech_key", match=models.MatchAny(any=keys)
                    ),
                    models.FieldCondition(
                        key="source", match=models.MatchValue(value="dip")
                    ),
                ]
            ),
            with_payload=[
                "speech_key",
                "source_item_id",
                "citation_url",
                "text",
                "chunk_index",
            ],
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
                str(dsid),
                {
                    "key": payload.get("speech_key"),
                    "texts": [],
                    "citation_url": payload.get("citation_url"),
                },
            )
            entry["texts"].append(
                (payload.get("chunk_index") or 0, payload.get("text") or "")
            )
        if next_offset is None:
            break

    # Match each op speech to its true DIP twin by normalized-text similarity.
    graft_ops: list[tuple[str, str]] = []  # (op_source_item_id, pdf_url)
    delete_dip_sids: list[str] = []
    for op_sid, op in op_speeches.items():
        op_norm = _norm_speech_text(_join_indexed_texts(op["texts"]))
        if not op_norm:
            continue
        for dsid, dip in dip_speeches.items():
            if dip["key"] != op["key"] or dsid in delete_dip_sids:
                continue
            dip_norm = _norm_speech_text(_join_indexed_texts(dip["texts"]))
            if not dip_norm:
                continue
            # autojunk=False is load-bearing: the default auto-junk heuristic
            # treats characters occurring in >1% of a 200+-char sequence as
            # junk, which on long normalized speech text collapses real twins
            # to ratios far below the threshold (official 21/90 data: only
            # 15/76 same-key pairs cleared 0.85 with autojunk on; all 76 score
            # 0.92+ with it off). Must stay symmetric with the DIP
            # resurrection guard's comparator.
            ratio = difflib.SequenceMatcher(
                None, op_norm, dip_norm, autojunk=False
            ).ratio()
            if ratio >= _SUPERSEDE_TEXT_MATCH_RATIO:
                if dip["citation_url"]:
                    # str() is load-bearing: MatchValue accepts only bool/int/str.
                    graft_ops.append((str(op_sid), dip["citation_url"]))
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
                    models.FieldCondition(
                        key="source", match=models.MatchValue(value="dip")
                    ),
                ]
            )
        ),
        wait=True,
    )
    # operator visibility on the merge + duplicate deletion.
    print(
        f"supersede: grafted DIP transcript PDF onto {len(graft_ops)} op speech(es), "
        f"then deleted {len(delete_dip_sids)} matched DIP twin(s)",
        file=sys.stderr,
    )
    return len(delete_dip_sids)
