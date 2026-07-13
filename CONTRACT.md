# wahl.chat V2 Data Contract

_Auto-generated from Pydantic models — do not edit manually._
_Regenerate with: `cd ai-backend && PYTHONPATH=src uv run python ../scripts/generate_contract.py`_

---

## Corpus Models

These models define the shape of data flowing through the ingestion pipeline into
Qdrant (Phase 5: Firestore and GCS stores removed — D-10).

## ChunkRecord

Payload stored alongside each Qdrant vector point.

    Design: shared ENVELOPE + source-owned nested ``meta`` object.
      - Indexed fields (tenant key, region, date, source type, etc.) stay top-level
        so Qdrant payload indexes remain effective.
      - Non-indexed source-specific descriptive fields move into ``meta``
        (a typed builder model dumped to dict at the connector boundary).
      - ``exclude_none=True`` on model_dump keeps absent envelope fields and
        None meta out of Qdrant — no NULL columns.

    Envelope fields (top-level, all sources):
        chunk_key, source_item_id, chunk_index, text, party_id, region,
        authority_tier, source_type, publish_date, citation_url, citation_title,
        external_id, party_ids, status, as_of_date, claim_id, wahlperiode,
        speech_key, source, meta.

    vote_record meta (VoteMeta): vote_results, motion_outcome.
    parliamentary_speech meta (SpeechMeta): person_id, speaker_name,
        xml_rede_id, protocol_id, protocol_api_id.

    Note: the Qdrant point ID is computed externally via compute_chunk_id().
    This model carries NO region_path field — only the scalar region.
    Cursor + pledge fields: external_id (Qdrant cursor), status/as_of_date/claim_id (pledge payload).
    Vote-record fields: party_ids (participating parties, filterable array; INDEXED top-level).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chunk_key` | `string` | Yes | Human-readable '{source_item_id}:{chunk_index:04d}' — PAYLOAD only, not the point ID |
| `source_item_id` | `string` | Yes | Parent source item UUID |
| `chunk_index` | `integer` | Yes | Zero-based chunk position within the item |
| `text` | `string` | Yes | Chunk text content |
| `party_id` | `string` | Yes | Short party slug, e.g. 'spd' |
| `region` | `string` | Yes | Scalar region for MatchAny filter |
| `authority_tier` | `AuthorityTier` | Yes | Trustworthiness tier |
| `source_type` | `SourceType` | Yes | Content category |
| `publish_date` | `string` | Yes | Date the source was published |
| `citation_url` | `string` | No | URL for SSE citation annotation |
| `citation_title` | `string` | No | Title for SSE citation annotation |
| `external_id` | `integer` | No | Monotonic integer source ID for the Qdrant cursor. Set to the raw AW poll integer for vote_record chunks; None for pledges (no monotonic integer ID) and other source types. |
| `status` | `string` | No | Pledge fulfillment status (PledgeStatus enum value) — pledge chunks only |
| `as_of_date` | `string` | No | Date the pledge status was assessed — pledge chunks only |
| `claim_id` | `string` | No | Pledge claim identifier for cross-party lookup — pledge chunks only |
| `party_ids` | `array[string]` | No | Sorted list of canonical slugs of every party that participated in the vote — filterable via a non-tenant keyword array index. vote_record only. |
| `wahlperiode` | `integer` | No | German legislative period (Wahlperiode) number, e.g. 19 for 19th Bundestag. Stamped by the connector at normalize() time. |
| `legislature_period_id` | `integer` | No | AW parliament_period ID for the legislature this vote belongs to. Globally unique integer, e.g. 161 for 21st Bundestag (2025-), 149 for Bayern 2023-2028. Used for period-scoped retrieval. None for legacy chunks ingested before Phase 7. |
| `relevance_levels` | `array[string]` | No | Governance levels at which this vote is relevant. Values from {'federal', 'state', 'municipal'}. Set by AW connector normalize() from field_topics taxonomy lookup. None for non-vote chunks. |
| `speech_key` | `string` | No | Deterministic cross-source speech dedup identity `de-{ep}-{session}-{speaker_slug}-{agenda_slug}` (src/ingestion/speech_key.py). Written by BOTH the op and DIP connectors; the supersede-delete filter and the DIP pre-insert resurrection-guard key (D-06/D-07). INDEXED keyword. None on legacy chunks until the 11-07 migration stamps them. |
| `source` | `string` | No | Connector discriminator, values 'dip' | 'op'. Drives the source-scoped cursor (run.py::get_cursor) so op and DIP do not share a cursor (D-11). INDEXED keyword. None on legacy chunks until the 11-07 migration stamps them. |
| `content_hash` | `string` | No | Stable hash of the chunk's meaningful content (text + source-specific payload). Lets re-ingestion detect and apply upstream corrections. None when the connector does not compute it. |
| `meta` | `object` | No | Source-owned nested metadata. Connectors pass a typed builder (VoteMeta or SpeechMeta) dumped via model_dump(mode='json', exclude_none=True). Not indexed — do not filter on meta.* fields in Qdrant. |

### Corpus Enums

## AuthorityTier

Trustworthiness tier for a data source item.

| Value |
|-------|
| `authoritative` |
| `factual_record` |
| `self_reported` |
| `promotional` |

## SourceType

Content category of the source item.

| Value |
|-------|
| `party_manifesto` |
| `vote_record` |
| `drucksache` |
| `qa_transcript` |
| `pledge_record` |
| `parliamentary_speech` |

---

## Derived / External Sources (Pledge Contract)

Pledge records represent the fulfillment status of political pledges tracked by
external sources (e.g. the Cambridge PledgeTracker project). Phase 5 (D-04):
pledges are embedded into Qdrant as ChunkRecords with `source_type=pledge_record`.
The filterable fields `status`, `as_of_date`, and `claim_id` live on `ChunkRecord`
(Qdrant payload indexes) — no separate Firestore pledges/ collection.

**Key design decisions (D-04..D-06):**

- **D-04:** Pledge records ARE embedded into Qdrant as ChunkRecords (Phase-5 reversal
  of Phase-2 no-embed decision). `source_type=pledge_record` distinguishes them.
- **D-05:** `status`, `as_of_date`, and `claim_id` are Qdrant payload fields
  on ChunkRecord, enabling per-status / per-claim Qdrant filtering.
- **D-06:** Pledge fulfillment status is public governmental commitment data, NOT
  GDPR Art. 9 special-category data — embedding is permitted.
- **Phase 5 removed:** `src/matcher/` package (Topic, Claim, Question,
  QuestionStancePair Firestore models) — deleted in D-10.

### Pledge Enums

## PledgeStatus

Fulfillment status of a political pledge.

    Values are intentionally stable — Cambridge PledgeTracker endpoint
    may use equivalent but differently-named categories; map on ingestion.

| Value |
|-------|
| `fulfilled` |
| `partially_fulfilled` |
| `in_progress` |
| `broken` |
| `stalled` |
| `not_yet_started` |

## PledgeEventType

Type of event recorded against a pledge.

    Provisional — may be refined against the Cambridge endpoint.

| Value |
|-------|
| `progress` |
| `reversal` |
| `announcement` |
| `legislation` |
| `budget` |
| `deadline_missed` |
| `completed` |

---

## SC6 Review Sign-off

> **Status:** APPROVED
> **Reviewer:** Annika Siefke
> **Date:** 2026-06-07
> **Gate:** SC6 — derived/external pledge contract reviewed and agreed before Phase 3 connector work begins.
>
> ⚠️ **Superseded.** Phase-5 D-04 supersedes Phase-2 decisions D-01..D-05: pledge records are now embedded into Qdrant as ChunkRecords with source_type=pledge_record (not stored as Firestore records). The Phase-2 SC6 sign-off (status APPROVED, 2026-06-07) transitively covers the superseded Firestore-pledge design; a fresh Phase-5 SC6 sign-off against the regenerated single-store CONTRACT.md may be warranted at the developer's discretion.
>
> The "Derived / External Sources (Pledge Contract)" section above (Phase-2 pledge design:
> PledgeStatus, PledgeEventType) has been reviewed and explicitly approved:
>
> - Pledge records are never embedded into Qdrant. They are a derived, external source maintained in Firestore only.
> - `grounded_in[]` points to `source_item_ids` (pledge→corpus, one-directional, D-02).
> - Pledge keying is `{party_id}_{claim_id}_{region}` with `party_id`, `claim_id`, `region`, and `as_of_date` as queryable indexed top-level fields — `where("party_id","==","spd")` is supported (D-03, not hash-only).
> - `PledgeStatus` / `PledgeEventType` vocabulary is accepted as a provisional Phase-2 snapshot; `raw` buffer absorbs Cambridge-endpoint drift (D-04).
> - `claims/` shape `{text, party_id, topic_id?, region, made_on}` is agreed (D-05).
>
> Phase 3 connector work is **unblocked**.
