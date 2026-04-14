# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared citation utilities for guided exploration.

Single source of truth for creating, extracting, and resolving citations.
All citation handling should go through these functions.
"""

import logging
import re

from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.exploration import RetrievedChunk

logger = logging.getLogger(__name__)


def create_citation_from_chunk(
    chunk: RetrievedChunk,
    party_name: str,
) -> Citation:
    """Create a Citation from a RAG chunk.

    Args:
        chunk: The retrieved chunk from Qdrant
        party_name: Display name of the party (e.g., "SPD", not "spd")

    Returns:
        Citation with chunk_id as ID and display party name
    """
    page_raw = chunk.source_page
    page_number = (int(page_raw) + 1) if page_raw is not None else None
    doc_name = chunk.metadata.get("document_name", chunk.source_document)

    return Citation(
        id=chunk.chunk_id,
        party=party_name,
        document=doc_name,
        section=chunk.source_section,
        page=page_number,
        document_publish_date=chunk.metadata.get("document_publish_date"),
        url=chunk.metadata.get("url"),
        source_document=chunk.metadata.get("source_document"),
    )


def extract_used_citations(
    text: str,
    all_citations: list[Citation],
) -> list[Citation]:
    """Extract only the citations that were actually used in the text.

    Parses the text for [citation-id] markers and returns only
    the citations that were referenced.

    Handles both single citations [id] and multiple [id1, id2].
    Skips [PARTY:...] markers used for party-section formatting and
    [PARTY_BADGE:id] markers used for inline party pills in chat text.

    Args:
        text: The generated text with inline citations
        all_citations: All available citations

    Returns:
        List of citations that were actually used in the text
    """
    bracket_pattern = r"\[([^\]]+)\]"
    bracket_contents = re.findall(bracket_pattern, text)

    used_ids: set[str] = set()
    for content in bracket_contents:
        if "PARTY:" in content or content.startswith("PARTY_BADGE:"):
            continue
        for id_part in content.split(","):
            id_part = id_part.strip()
            if id_part:
                used_ids.add(id_part)

    used_citations = [c for c in all_citations if c.id in used_ids]

    logger.debug(
        f"Citation extraction: found {len(used_ids)} IDs in text, "
        f"matched {len(used_citations)} of {len(all_citations)} available"
    )

    return used_citations
