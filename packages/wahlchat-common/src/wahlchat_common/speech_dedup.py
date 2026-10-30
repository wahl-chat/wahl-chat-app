# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Collapse DIP twins of openparliament.tv speeches in fetched payloads.

Shared because two readers need the same answer to "which speeches are
distinct": chat retrieval (``ai-backend/src/retrieve.py``) and the parliament
feed, which builds its sitting days from the same corpus.
"""

from __future__ import annotations

from typing import Any


def dedup_prefer_op(payloads: list[dict]) -> list[dict]:
    """Collapse a DIP twin into its op counterpart ONLY when the match is unambiguous.

    Post-fetch, pure-Python dedup for ``parliamentary_speech`` payloads. The SAME
    real-world speech can surface as both a ``source=="dip"`` and
    a ``source=="op"`` chunk sharing one ``speech_key``. The op member carries the
    video AND the full speech text, so it is a complete substitute for its DIP
    twin — dropping a *matched* twin loses nothing.

    Why the match must be counted, not assumed 1:1
    ------------------------------------------------
    ``speech_key`` (``de-{ep}-{session}-{speaker}-{agenda}``) is NOT unique per
    speech and there is no exact shared op↔DIP id (op ``speechIndex`` ≠ DIP
    rede-seq; the proceedings text matches only ~99%, not byte-for-byte). Two
    situations put several records under one key:
      * a long speech chunked into several records (shared key + source_item_id);
      * a speaker who speaks twice under the same agenda item — two DISTINCT
        speeches with the same key but DIFFERENT ``source_item_id``.
    Blindly dropping every DIP member whose key an op owns would delete a distinct
    DIP speech that op does NOT have — a grounding/coverage loss.

    Rule (provably lossless, no similarity threshold)
    -------------------------------------------------
    Group by ``speech_key`` and count DISTINCT speeches per source via
    ``source_item_id``:
      * exactly ONE op speech AND exactly ONE dip speech under the key → genuine
        twins → keep the op (all its chunks), graft the dip's transcript PDF, drop
        the dip (all its chunks);
      * any other shape (≥2 distinct op or ≥2 distinct dip, or op-only, or
        dip-only) → keep EVERYTHING. Distinct speeches are never merged; at worst
        the rare true-collision group shows both an op and a dip record (both
        correctly attributed). A missing / None ``speech_key`` is always kept.
    First-seen order is preserved; only matched dip twins are removed.

    This is NEVER a Qdrant ``source`` filter — filtering the query on ``source``
    would break the vote-level down-rank and the two-pass retrieval and violate the
    tenant-only HNSW selective-filter rule. Dedup is post-fetch, exactly like the
    vote-level down-rank.

    Args:
        payloads: Speech payload dicts as returned post-fetch (each may carry
            ``speech_key``, ``source`` and ``source_item_id``).

    Returns:
        The deduped payload list (same dict objects), all op members preserved.
    """
    # Per key: the distinct op / dip speeches (by source_item_id) and the op
    # payload to graft onto. A chunk without a source_item_id counts as its own
    # distinct speech (its id() keeps it from collapsing an unrelated one).
    op_sids: dict[Any, set] = {}
    dip_sids: dict[Any, set] = {}
    op_graft_target: dict[Any, dict] = {}
    for payload in payloads:
        key = payload.get("speech_key")
        if key is None:
            continue
        sid = payload.get("source_item_id", id(payload))
        if payload.get("source") == "op":
            op_sids.setdefault(key, set()).add(sid)
            op_graft_target.setdefault(key, payload)
        elif payload.get("source") == "dip":
            dip_sids.setdefault(key, set()).add(sid)

    def _is_unambiguous_twin(key: Any) -> bool:
        return len(op_sids.get(key, ())) == 1 and len(dip_sids.get(key, ())) == 1

    result: list[dict] = []
    for payload in payloads:
        key = payload.get("speech_key")
        if key is None:
            result.append(payload)  # keyless → never a duplicate
            continue
        if payload.get("source") == "dip" and _is_unambiguous_twin(key):
            # Genuine 1:1 twin of an op speech → graft its PDF and drop it.
            _graft_transcript_pdf(op=op_graft_target[key], dip=payload)
            continue
        result.append(payload)
    return result


def _graft_transcript_pdf(*, op: dict, dip: dict) -> None:
    """Copy a DIP duplicate's transcript PDF onto the surviving op payload.

    Sets ``op["meta"]["transcript_pdf_url"]`` from the dip payload's
    ``citation_url`` (its plenary-protocol PDF) when the op record does not
    already carry one — the query-time mirror of the ingest-time graft in
    ``supersede_dip_duplicates``, so a dual-format speech source works even for
    corpora ingested before the merge landed. Mutates ``op`` in place; no-op when
    the dip has no citation_url.
    """
    pdf_url = dip.get("citation_url")
    if not pdf_url:
        return
    existing_meta = op.get("meta")
    if isinstance(existing_meta, dict) and existing_meta.get("transcript_pdf_url"):
        return  # op already carries a transcript link — keep it.
    # Shallow-copy the meta before setting, so we never mutate a meta dict that may
    # be aliased elsewhere in the retrieval pass; the copy is what op now points at.
    new_meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    new_meta["transcript_pdf_url"] = pdf_url
    op["meta"] = new_meta
