# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""RAG service for guided exploration using Qdrant."""

import logging
import os
from uuid import uuid4

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from src.guided_exploration.models.exploration import RetrievedChunk
from src.guided_exploration.services.study_context import (
    STUDY_CONTEXT_PREFIX,
    get_study_topic,
    is_study_context,
)
from src.guided_exploration.services.study_positions_rag import StudyPositionsRAG

logger = logging.getLogger(__name__)

# Get environment suffix for collection names
env = os.getenv("ENV", "dev")
env_suffix = f"_{env}" if env in ["prod", "dev"] else "_dev"

# Legacy context that uses the old collection naming scheme
LEGACY_CONTEXT_ID = "bundestagswahl-2025"
LEGACY_COLLECTION_NAME = f"all_parties{env_suffix}"


def get_context_collection_name(context_id: str) -> str:
    """Get the Qdrant collection name for party documents in a given context."""
    # Legacy context uses old collection naming (party_docs_dev/party_docs_prod)
    if context_id == LEGACY_CONTEXT_ID:
        return LEGACY_COLLECTION_NAME
    return f"context_{context_id}_party_docs{env_suffix}"


class RAGService:
    """
    RAG service for retrieving document chunks from Qdrant.

    Uses embeddings to search for relevant documents and returns
    structured RetrievedChunk objects for use in the exploration flow.

    For study sessions (``context_id`` starting with ``study-``), retrieval
    is routed to an in-memory ``StudyPositionsRAG`` over ~200 precomputed
    fake-manifesto positions — no Qdrant call is made.
    """

    # Class-level cache: the study resolver loads ~1 MB of vectors once
    # and is reused across all RAGService instances.
    _study_rag: StudyPositionsRAG | None = None

    def __init__(
        self,
        embeddings: Embeddings,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._client = QdrantClient(
            url=qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=qdrant_api_key or os.getenv("QDRANT_API_KEY"),
        )

    def _get_study_rag(self) -> StudyPositionsRAG:
        """Lazily instantiate the in-memory study positions resolver."""
        if RAGService._study_rag is None:
            RAGService._study_rag = StudyPositionsRAG(embeddings=self._embeddings)
        return RAGService._study_rag

    async def retrieve_chunks_for_parties(
        self,
        query: str,
        context_id: str,
        parties: list[str],
        n_docs: int = 3,
        score_threshold: float = 0.5,
    ) -> list[RetrievedChunk]:
        """Fan out per-party retrieval and concatenate results.

        Used by the quick-summary and factual-query paths where the LLM is
        shown a single flat chunk list grouped by party.
        """
        all_chunks: list[RetrievedChunk] = []
        for party_id in parties:
            chunks = await self.retrieve_chunks_for_party(
                query=query,
                context_id=context_id,
                party_id=party_id,
                n_docs=n_docs,
                score_threshold=score_threshold,
            )
            all_chunks.extend(chunks)
        return all_chunks

    async def retrieve_chunks_for_party(
        self,
        query: str,
        context_id: str,
        party_id: str,
        n_docs: int = 5,
        score_threshold: float = 0.5,
    ) -> list[RetrievedChunk]:
        """
        Retrieve document chunks from Qdrant for a specific party.

        Args:
            query: The search query (should be RAG-optimized)
            context_id: The context ID (e.g., 'bundestagswahl-2025')
            party_id: The party ID to filter by
            n_docs: Maximum number of documents to retrieve
            score_threshold: Minimum relevance score

        Returns:
            List of RetrievedChunk objects
        """
        # Study sessions: route to in-memory fake-manifesto resolver.
        # Each chunk becomes one position directly (no extraction), so
        # n_docs ≈ target positions per party. Caller controls the cap:
        # the tree builder explicitly passes n_docs=10 to see the full
        # per-party payload; chat-style paths (quick summary, followup)
        # pass smaller numbers so the LLM gets a focused slice instead
        # of every available claim.
        if is_study_context(context_id):
            return await self._get_study_rag().retrieve_chunks_for_party(
                query=query,
                party_id=party_id,
                topic=get_study_topic(context_id),
                n_docs=n_docs,
            )

        collection_name = get_context_collection_name(context_id)

        # Check if collection exists
        collections = self._client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name not in collection_names:
            logger.warning(
                f"Collection {collection_name} not found. "
                f"Available: {collection_names}"
            )
            return []

        # Generate query embedding
        query_vector = await self._embeddings.aembed_query(query)

        # Build filter for party namespace
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="namespace",
                    match=MatchValue(value=party_id),
                )
            ]
        )

        logger.info(
            f"RAG search: collection={collection_name}, party={party_id}, "
            f"query='{query}', n_docs={n_docs}, score_threshold={score_threshold}"
        )

        # Search Qdrant
        search_result = self._client.search(
            collection_name=collection_name,
            query_vector=("dense", query_vector),
            limit=n_docs,
            with_payload=True,
            query_filter=filter_condition,
            score_threshold=score_threshold,
        )

        # Convert to RetrievedChunk objects
        chunks = []
        for point in search_result:
            if point.payload is None:
                continue

            chunks.append(
                RetrievedChunk(
                    chunk_id=f"{party_id}-{uuid4().hex[:8]}",
                    content=point.payload.get("text", ""),
                    party_id=party_id,
                    source_document=point.payload.get("source", "Wahlprogramm"),
                    source_section=point.payload.get("section"),
                    source_page=point.payload.get("page"),
                    relevance_score=point.score,
                    metadata={
                        k: v
                        for k, v in point.payload.items()
                        if k not in ("text", "namespace")
                    },
                )
            )

        logger.info(
            f"Retrieved {len(chunks)} chunks for party {party_id} "
            f"(query: {query[:50]}...)"
        )

        return chunks
