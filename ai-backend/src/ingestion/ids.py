# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import uuid

# Generated once with uuid.uuid5(uuid.NAMESPACE_DNS, "v2.wahl.chat").
# MUST NOT be changed — changing it shifts all IDs and breaks idempotency.
WAHL_CHAT_NS = uuid.UUID("5c7a578f-9c8f-5b26-b9f3-457f1fef0890")


def compute_source_item_id(source_type: str, external_id: str) -> uuid.UUID:
    """Deterministic source item ID: same source_type + external_id always yields the same UUID."""
    return uuid.uuid5(WAHL_CHAT_NS, f"{source_type}:{external_id}")


def compute_chunk_id(source_item_id: uuid.UUID, chunk_index: int) -> uuid.UUID:
    """Deterministic chunk point ID for Qdrant (must be UUID, not string)."""
    return uuid.uuid5(WAHL_CHAT_NS, f"{str(source_item_id)}:{chunk_index}")


def make_chunk_key(source_item_id: uuid.UUID, chunk_index: int) -> str:
    """Human-readable payload key stored in chunk_key field — never used as the Qdrant point ID."""
    return f"{str(source_item_id)}:{chunk_index:04d}"
