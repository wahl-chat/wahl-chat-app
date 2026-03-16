# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Orchestrator for guided exploration with per-party parallel architecture.

Coordinates the 3-phase flow:
1. Per-Party Topic Resolution (parallel) - RAG + topic extraction per party
2. Topic Combining - Merge party trees into unified structure + send to frontend
3. Per-Party Knowledge Resolution (parallel) - Resolve knowledge per party
4. Merge into KnowledgeBase
"""

import asyncio
import logging
from uuid import uuid4

from src.firebase_service import aget_context_by_id, aget_parties_for_context
from src.guided_exploration.agents.knowledge_resolver import (
    PartyKnowledgeResolverAgent,
    PartyKnowledgeResolverInput,
)
from src.guided_exploration.agents.llm_provider import LLMRegistry, LLMTier
from src.guided_exploration.agents.party_context import PartyInfo, parties_to_info_map
from src.guided_exploration.agents.party_topic_resolver import (
    PartyTopicResolverAgent,
    PartyTopicResolverInput,
)
from src.guided_exploration.agents.topic_combiner import (
    TopicCombinerAgent,
    TopicCombinerInput,
)
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    BreadcrumbItem,
    BreadcrumbLevel,
    ExplorationReadyEvent,
    NavigationState,
    ThinkingEvent,
    TopicTreeEvent,
)
from src.guided_exploration.models.errors import InsufficientChunksError
from src.guided_exploration.models.exploration import (
    KnowledgeBase,
    PartyKnowledge,
    PartyTopicTree,
    RetrievedChunk,
)
from src.guided_exploration.models.tree import TopicTree
from src.guided_exploration.services.knowledge_merger import merge_party_knowledge
from src.guided_exploration.services.rag_service import RAGService

logger = logging.getLogger(__name__)

# Timeout for per-party operations
PARTY_TIMEOUT_SECONDS = 30.0


class Orchestrator:
    """
    Orchestrates the guided exploration flow with per-party parallel architecture.

    Key principles:
    1. Each party is planned separately (RAG + topic extraction)
    2. TopicCombiner merges all party trees into unified structure
    3. Topic tree is sent to frontend immediately (before knowledge resolution)
    4. Each party's knowledge is resolved in parallel
    5. Knowledge merged into unified KnowledgeBase
    """

    def __init__(
        self,
        sse_manager: SSEManager,
        llm_registry: LLMRegistry,
    ) -> None:
        self._sse = sse_manager
        self._llm_registry = llm_registry
        self._rag_service = RAGService(embeddings=llm_registry.embeddings)

        # Topic resolution and combining require good reasoning capabilities
        self._party_topic_resolver = PartyTopicResolverAgent(
            self._llm_registry.get(LLMTier.BALANCED)
        )
        self._topic_combiner = TopicCombinerAgent(
            self._llm_registry.get(LLMTier.BALANCED)
        )
        # Knowledge resolution benefits from deeper reasoning
        # Also provide RAG retriever for per-subtopic targeted retrieval
        # and fast LLM for query rewriting
        self._party_knowledge_resolver = PartyKnowledgeResolverAgent(
            llm_provider=self._llm_registry.get(LLMTier.REASONING),
            rag_retriever=self._retrieve_chunks_for_party,
            fast_llm_provider=self._llm_registry.get(LLMTier.FAST),
        )

    async def start_exploration(
        self,
        session_id: str,
        query: str,
        context_id: str,
        parties: list[str],
        rag_query: str | None = None,
    ) -> tuple[str, TopicTree, KnowledgeBase]:
        """
        Start a new exploration with per-party parallel architecture.

        Flow:
        1. Per-Party Topic Resolution (parallel)
        2. Topic Combining + send TopicTreeEvent to frontend
        3. Per-Party Knowledge Resolution (parallel)
        4. Merge into KnowledgeBase

        Args:
            session_id: The session ID for SSE events
            query: The user's original query (for display/context)
            context_id: The election/political context ID
            parties: Party IDs to include in exploration
            rag_query: Optimized query for RAG retrieval (defaults to query)

        Returns:
            Tuple of (exploration_id, TopicTree, KnowledgeBase)
        """
        # Use rag_query for retrieval, query for context/display
        retrieval_query = rag_query or query
        exploration_id = str(uuid4())

        # Fetch context and party info from Firebase
        context_name, parties_info = await self._get_context_info(context_id, parties)

        # =====================================================================
        # PHASE 1: Per-Party Topic Resolution (parallel)
        # =====================================================================
        await self._send_thinking(
            session_id,
            "retrieving",
            f"Analysiere Wahlprogramme von {len(parties)} Parteien...",
        )

        logger.info(f"Phase 1: Starting topic resolution for {len(parties)} parties")

        party_trees, party_chunks = await self._phase1_topic_resolution(
            session_id=session_id,
            query=query,
            rag_query=retrieval_query,
            context_id=context_id,
            context_name=context_name,
            parties=parties,
            parties_info=parties_info,
        )

        if not party_trees:
            logger.error("No party trees resolved - cannot continue")
            raise ValueError("No party topic trees could be resolved")

        # Validate chunk coverage - ensure enough parties have chunks
        self._validate_chunk_coverage(parties, party_chunks, parties_info)

        # =====================================================================
        # PHASE 2: Combine Topic Trees + Send to Frontend
        # =====================================================================
        await self._send_thinking(
            session_id,
            "planning",
            "Strukturiere Themen...",
        )

        logger.info(f"Phase 2: Combining {len(party_trees)} party trees")

        combiner_output = await self._topic_combiner.execute(
            TopicCombinerInput(
                query=query,
                context_id=context_id,
                context_name=context_name,
                party_trees=party_trees,
                parties=parties_info,
            )
        )

        topic_tree = combiner_output.topic_tree
        topic_tree.exploration_id = exploration_id
        party_coverage = combiner_output.party_coverage

        # Send TopicTreeEvent immediately - frontend can show tree while we resolve knowledge
        await self._send_topic_tree(session_id, exploration_id, topic_tree)

        # =====================================================================
        # PHASE 3: Per-Party Knowledge Resolution (parallel)
        # =====================================================================
        await self._send_thinking(
            session_id,
            "generating",
            "Extrahiere Parteipositionen...",
        )

        logger.info(
            f"Phase 3: Starting knowledge resolution for {len(party_trees)} parties"
        )

        party_knowledge = await self._phase3_knowledge_resolution(
            session_id=session_id,
            context_id=context_id,
            context_name=context_name,
            topic_tree=topic_tree,
            party_chunks=party_chunks,
            party_coverage=party_coverage,
            parties_info=parties_info,
        )

        # =====================================================================
        # PHASE 4: Merge into KnowledgeBase
        # =====================================================================
        logger.info(f"Phase 4: Merging knowledge from {len(party_knowledge)} parties")

        knowledge_base = merge_party_knowledge(topic_tree, party_knowledge)

        logger.info(
            f"Exploration {exploration_id} complete: "
            f"{len(topic_tree.topics)} topics, "
            f"{len(knowledge_base.subtopics)} subtopics with knowledge"
        )

        # Send ExplorationReadyEvent - KB is fully loaded
        logger.info(f"Sending ExplorationReadyEvent for {exploration_id}")
        sent = await self._sse.send_to_session(
            session_id,
            ExplorationReadyEvent(
                exploration_id=exploration_id,
                topics_count=len(topic_tree.topics),
                subtopics_count=len(knowledge_base.subtopics),
                parties_count=len(party_knowledge),
            ),
        )
        logger.info(f"ExplorationReadyEvent sent: {sent}")

        return exploration_id, topic_tree, knowledge_base

    async def _get_context_info(
        self,
        context_id: str,
        party_ids: list[str],
    ) -> tuple[str, dict[str, PartyInfo]]:
        """
        Fetch context name and party info from Firebase.

        Args:
            context_id: The context ID
            party_ids: List of party IDs to fetch info for

        Returns:
            Tuple of (context_name, {party_id: PartyInfo})
        """
        # Fetch context
        context = await aget_context_by_id(context_id)
        context_name = context.name if context else context_id

        # Fetch all parties for context
        all_parties = await aget_parties_for_context(context_id)
        all_parties_map = parties_to_info_map(all_parties)

        # Filter to only requested party IDs
        parties_info = {
            pid: all_parties_map[pid] for pid in party_ids if pid in all_parties_map
        }

        return context_name, parties_info

    def _validate_chunk_coverage(
        self,
        requested_parties: list[str],
        party_chunks: dict[str, list[RetrievedChunk]],
        parties_info: dict[str, PartyInfo],
    ) -> None:
        """
        Validate that enough parties have retrieved chunks.

        Raises InsufficientChunksError if:
        - Fewer than 2 parties have chunks, OR
        - Fewer than 50% of requested parties have chunks

        Args:
            requested_parties: List of party IDs that were requested
            party_chunks: Mapping of party_id to retrieved chunks
            parties_info: Mapping of party_id to PartyInfo for display names
        """
        total_parties = len(requested_parties)

        # Count parties with at least 1 chunk
        parties_with_chunks = [
            pid for pid in requested_parties if len(party_chunks.get(pid, [])) > 0
        ]
        count_with_chunks = len(parties_with_chunks)

        # Find parties without chunks
        parties_without_chunks = [
            pid for pid in requested_parties if pid not in parties_with_chunks
        ]

        # Get display names for parties without chunks
        party_names_without_chunks = [
            parties_info.get(
                pid,
                PartyInfo(
                    party_id=pid,
                    name=pid.upper(),
                    long_name=pid.upper(),
                    description=None,
                ),
            ).name
            for pid in parties_without_chunks
        ]

        # Log for debugging
        logger.info(
            f"Chunk coverage: {count_with_chunks}/{total_parties} parties have chunks"
        )
        if parties_without_chunks:
            logger.warning(
                f"Parties without chunks: {', '.join(parties_without_chunks)}"
            )

        # Validation thresholds:
        # - At least 2 parties must have chunks
        # - At least 50% of requested parties must have chunks
        min_parties_threshold = 2
        min_percentage_threshold = 0.5

        coverage_percentage = (
            count_with_chunks / total_parties if total_parties > 0 else 0
        )

        if (
            count_with_chunks < min_parties_threshold
            or coverage_percentage < min_percentage_threshold
        ):
            logger.error(
                f"Insufficient chunk coverage: {count_with_chunks}/{total_parties} "
                f"({coverage_percentage:.0%}) parties have chunks. "
                f"Missing: {', '.join(party_names_without_chunks)}"
            )
            raise InsufficientChunksError(
                message=(
                    f"Insufficient document chunks: only {count_with_chunks} of "
                    f"{total_parties} parties have relevant content"
                ),
                total_parties=total_parties,
                parties_with_chunks=count_with_chunks,
                parties_without_chunks=party_names_without_chunks,
            )

    async def _phase1_topic_resolution(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        context_id: str,
        context_name: str,
        parties: list[str],
        parties_info: dict[str, PartyInfo],
    ) -> tuple[dict[str, PartyTopicTree], dict[str, list[RetrievedChunk]]]:
        """
        Phase 1: Resolve topics for each party in parallel.

        Args:
            query: Original user query (for topic resolution context)
            rag_query: Optimized query (for RAG retrieval)

        Returns:
            Tuple of (party_trees, party_chunks)
        """

        async def resolve_for_party(
            party_id: str,
        ) -> tuple[str, PartyTopicTree | None, list[RetrievedChunk]]:
            try:
                # RAG retrieval for this party using optimized rag_query
                chunks = await self._retrieve_chunks_for_party(
                    rag_query, context_id, party_id
                )

                # Get party info (with fallback)
                party_info = parties_info.get(
                    party_id,
                    PartyInfo(
                        party_id=party_id,
                        name=party_id.upper(),
                        long_name=party_id.upper(),
                        description=None,
                    ),
                )

                # Resolve topics for this party
                result = await self._party_topic_resolver.execute(
                    PartyTopicResolverInput(
                        query=query,
                        context_id=context_id,
                        context_name=context_name,
                        party_id=party_id,
                        party_info=party_info,
                        retrieved_chunks=chunks,
                    )
                )

                return party_id, result.party_topic_tree, chunks

            except Exception as e:
                logger.error(f"Topic resolution failed for party {party_id}: {e}")
                return party_id, None, []

        # Run topic resolution for all parties in parallel with timeout
        tasks = [
            asyncio.wait_for(
                resolve_for_party(party_id),
                timeout=PARTY_TIMEOUT_SECONDS,
            )
            for party_id in parties
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        party_trees: dict[str, PartyTopicTree] = {}
        party_chunks: dict[str, list[RetrievedChunk]] = {}

        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"Phase 1 task failed: {result}")
                continue

            party_id, tree, chunks = result
            if tree is not None:
                party_trees[party_id] = tree
                party_chunks[party_id] = chunks

        return party_trees, party_chunks

    async def _phase3_knowledge_resolution(
        self,
        session_id: str,
        context_id: str,
        context_name: str,
        topic_tree: TopicTree,
        party_chunks: dict[str, list[RetrievedChunk]],
        party_coverage: dict[str, list[str]],
        parties_info: dict[str, PartyInfo],
    ) -> dict[str, PartyKnowledge]:
        """
        Phase 3: Resolve knowledge for each party in parallel.

        Returns:
            Mapping of party_id to PartyKnowledge
        """

        async def resolve_for_party(party_id: str) -> tuple[str, PartyKnowledge | None]:
            try:
                # Get party info (with fallback)
                party_info = parties_info.get(
                    party_id,
                    PartyInfo(
                        party_id=party_id,
                        name=party_id.upper(),
                        long_name=party_id.upper(),
                        description=None,
                    ),
                )

                result = await self._party_knowledge_resolver.execute(
                    PartyKnowledgeResolverInput(
                        context_id=context_id,
                        context_name=context_name,
                        party_id=party_id,
                        party_info=party_info,
                        topic_tree=topic_tree,
                        retrieved_chunks=party_chunks.get(party_id, []),
                        party_coverage=party_coverage,
                    )
                )

                return party_id, result.party_knowledge

            except Exception as e:
                logger.error(f"Knowledge resolution failed for party {party_id}: {e}")
                return party_id, None

        # Run knowledge resolution for all parties in parallel with timeout
        party_ids = list(party_chunks.keys())
        tasks = [
            asyncio.wait_for(
                resolve_for_party(party_id),
                timeout=PARTY_TIMEOUT_SECONDS,
            )
            for party_id in party_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        party_knowledge: dict[str, PartyKnowledge] = {}

        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"Phase 3 task failed: {result}")
                continue

            party_id, knowledge = result
            if knowledge is not None:
                party_knowledge[party_id] = knowledge

        return party_knowledge

    # =========================================================================
    # SSE Helpers
    # =========================================================================

    async def _send_thinking(
        self,
        session_id: str,
        stage: str,
        message: str,
    ) -> None:
        """Send a thinking event to the frontend."""
        await self._sse.send_to_session(
            session_id,
            ThinkingEvent(stage=stage, message=message),
        )

    async def _send_topic_tree(
        self,
        session_id: str,
        exploration_id: str,
        topic_tree: TopicTree,
    ) -> None:
        """Send the topic tree to the frontend."""
        navigation = NavigationState(
            exploration_id=exploration_id,
            current_path=[],
            breadcrumb=[
                BreadcrumbItem(
                    id="root",
                    name="Übersicht",
                    level=BreadcrumbLevel.ROOT,
                ),
            ],
        )

        await self._sse.send_to_session(
            session_id,
            TopicTreeEvent(
                exploration_id=exploration_id,
                tree=topic_tree,
                navigation=navigation,
            ),
        )

    # =========================================================================
    # RAG Retrieval
    # =========================================================================

    async def _retrieve_chunks_for_party(
        self,
        query: str,
        context_id: str,
        party_id: str,
    ) -> list[RetrievedChunk]:
        """Retrieve document chunks from Qdrant for a specific party."""
        return await self._rag_service.retrieve_chunks_for_party(
            query=query,
            context_id=context_id,
            party_id=party_id,
            n_docs=10,
            score_threshold=0.5,
        )
