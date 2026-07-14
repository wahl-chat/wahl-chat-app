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
        external_id, party_ids, wahlperiode,
        speech_key, source, meta.

    vote_record meta (VoteMeta): vote_results, motion_outcome.
    parliamentary_speech meta (SpeechMeta): person_id, speaker_name,
        xml_rede_id, protocol_id, protocol_api_id.

    Note: the Qdrant point ID is computed externally via compute_chunk_id().
    This model carries NO region_path field — only the scalar region.
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
| `external_id` | `integer` | No | Monotonic integer source ID for the Qdrant cursor. Set to the raw AW poll integer for vote_record chunks; None for source types without a monotonic integer ID. |
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
| `parliamentary_speech` |

---

## SC6 Review Sign-off

> **Status:** APPROVED
> **Reviewer:** Annika Siefke
> **Date:** 2026-06-07
> **Gate:** SC6 — derived/external source contract reviewed and agreed.
>
> The derived/external-source contract this gate originally covered (a
> commitment-fulfillment-tracking design, including its status/event enums
> and their ChunkRecord fields) was removed from the milestone — see quick
> task 260714-da9. This approval record is retained for provenance only; it
> no longer describes any contract present in the current schema.
