# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared formatting helpers for RAG context and party lists."""

from src.guided_exploration.models import Citation, RetrievedChunk
from src.guided_exploration.services.citation_utils import (
    create_citation_from_chunk as create_chunk_citation,
)


def format_rag_context(
    chunks: list[RetrievedChunk],
    party_map: dict,
) -> tuple[str, list[Citation]]:
    """Group chunks by party and render them with inline citation IDs."""
    if not chunks:
        return (
            "Keine relevanten Informationen in der Dokumentensammlung gefunden.",
            [],
        )

    citations: list[Citation] = []
    chunks_by_party: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        if chunk.party_id not in chunks_by_party:
            chunks_by_party[chunk.party_id] = []
        chunks_by_party[chunk.party_id].append(chunk)

        party = party_map.get(chunk.party_id)
        party_display = party.name if party else chunk.party_id
        citations.append(create_chunk_citation(chunk, party_display))

    context_parts = []
    for party_id, party_chunks in chunks_by_party.items():
        party = party_map.get(party_id)
        party_name = party.name if party else party_id
        context_parts.append(f"\n## {party_name}\n")
        for chunk in party_chunks:
            context_parts.append(f"[{chunk.chunk_id}] {chunk.content}\n\n")

    return "".join(context_parts), citations


def format_parties_list(party_ids: list[str], party_map: dict) -> str:
    """Render a markdown bullet list of parties with long names where available."""
    if not party_ids:
        return "Keine spezifischen Parteien"

    parts = []
    for party_id in party_ids:
        party = party_map.get(party_id)
        if party:
            parts.append(f"- {party_id}: {party.name} ({party.long_name})")
        else:
            parts.append(f"- {party_id}: {party_id.upper()}")

    return "\n".join(parts)
