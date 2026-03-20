# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Orchestrator for guided exploration with claim-based adaptive hierarchy.

Coordinates the 3-phase flow:
1. Per-Party RAG Retrieval + Claim Extraction (parallel)
2. Hierarchy Construction from all claims (single LLM call)
3. Send ExplorationTree to frontend

Knowledge resolution is eliminated — claims already contain the knowledge.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from src.firebase_service import aget_context_by_id, aget_parties_for_context
from src.guided_exploration.agents.claim_extractor import (
    ClaimExtractorAgent,
    ClaimExtractorInput,
)
from src.guided_exploration.agents.hierarchy_builder import (
    HierarchyBuilderAgent,
    HierarchyBuilderInput,
)
from src.guided_exploration.agents.llm_provider import LLMRegistry, LLMTier
from src.guided_exploration.agents.party_context import PartyInfo, parties_to_info_map
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    BreadcrumbItem,
    BreadcrumbLevel,
    ExplorationReadyEvent,
    NavigationState,
    ThinkingEvent,
    TopicTreeEvent,
)
from src.guided_exploration.models.claim import Claim, PartyClaims
from src.guided_exploration.models.errors import InsufficientChunksError
from src.guided_exploration.models.exploration import RetrievedChunk
from src.guided_exploration.models.tree import ExplorationNode, ExplorationTree
from src.guided_exploration.services.debug_logger import DebugLogger
from src.guided_exploration.services.rag_service import RAGService

logger = logging.getLogger(__name__)

# Timeout for per-party operations
PARTY_TIMEOUT_SECONDS = 60.0


class Orchestrator:
    """
    Orchestrates the guided exploration flow with claim-based architecture.

    Key principles:
    1. RAG retrieval + claim extraction per party in parallel
    2. All claims combined into a single hierarchy (LLM sees full picture)
    3. ExplorationTree sent to frontend — claims are the knowledge
    4. No separate knowledge resolution phase needed
    """

    def __init__(
        self,
        sse_manager: SSEManager,
        llm_registry: LLMRegistry,
    ) -> None:
        self._sse = sse_manager
        self._llm_registry = llm_registry
        self._rag_service = RAGService(embeddings=llm_registry.embeddings)

        # Claim extraction: factual, low temperature
        self._claim_extractor = ClaimExtractorAgent(
            self._llm_registry.get(LLMTier.BALANCED)
        )
        # Hierarchy building: needs good reasoning for structure
        self._hierarchy_builder = HierarchyBuilderAgent(
            self._llm_registry.get(LLMTier.REASONING)
        )

    async def start_exploration(
        self,
        session_id: str,
        query: str,
        context_id: str,
        parties: list[str],
        rag_query: str | None = None,
    ) -> tuple[str, ExplorationTree]:
        """
        Start a new exploration with claim-based adaptive hierarchy.

        Flow:
        1. Per-Party RAG + Claim Extraction (parallel)
        2. Hierarchy Construction (single LLM call)
        3. Send ExplorationTree to frontend

        Args:
            session_id: The session ID for SSE events
            query: The user's original query
            context_id: The election/political context ID
            parties: Party IDs to include
            rag_query: Optimized query for RAG retrieval (defaults to query)

        Returns:
            Tuple of (exploration_id, ExplorationTree)
        """
        retrieval_query = rag_query or query
        exploration_id = str(uuid4())

        # Initialize debug logger
        debug_logger = DebugLogger(
            session_id=session_id,
            query=query,
            parties=parties,
        )

        # Fetch context and party info from Firebase
        context_name, parties_info = await self._get_context_info(context_id, parties)

        # =====================================================================
        # PHASE 1: Per-Party RAG Retrieval + Claim Extraction (parallel)
        # =====================================================================
        await self._send_thinking(
            session_id,
            "retrieving",
            f"Analysiere Wahlprogramme von {len(parties)} Parteien...",
        )

        logger.info(
            f"Phase 1: Starting RAG + claim extraction for {len(parties)} parties"
        )

        all_claims, party_chunks = await self._phase1_claim_extraction(
            session_id=session_id,
            query=query,
            rag_query=retrieval_query,
            context_id=context_id,
            context_name=context_name,
            parties=parties,
            parties_info=parties_info,
            debug_logger=debug_logger,
        )

        if not all_claims:
            logger.error("No claims extracted - cannot continue")
            raise ValueError("No claims could be extracted from party documents")

        # Validate chunk coverage
        self._validate_chunk_coverage(parties, party_chunks, parties_info)

        # Validate claim quality — need enough data for a meaningful exploration
        claims_per_party: dict[str, int] = {}
        for claim in all_claims:
            claims_per_party[claim.party_id] = (
                claims_per_party.get(claim.party_id, 0) + 1
            )

        parties_with_claims = len(claims_per_party)
        min_claims_per_party = min(claims_per_party.values()) if claims_per_party else 0
        total_claims = len(all_claims)

        logger.info(
            f"Claim quality: {total_claims} total, "
            f"{parties_with_claims} parties, "
            f"min {min_claims_per_party} per party"
        )

        if total_claims < 15 or parties_with_claims < len(parties) or min_claims_per_party < 3:
            logger.warning(
                f"Insufficient claims for exploration: "
                f"{total_claims} total (need 15), "
                f"{parties_with_claims}/{len(parties)} parties with claims, "
                f"min {min_claims_per_party} per party (need 3)"
            )
            raise InsufficientChunksError(
                message=(
                    f"Nicht genug Informationen fuer eine Exploration: "
                    f"nur {total_claims} Positionen von {parties_with_claims} Parteien gefunden"
                ),
                total_parties=len(parties),
                parties_with_chunks=parties_with_claims,
                parties_without_chunks=[
                    parties_info.get(
                        pid,
                        PartyInfo(
                            party_id=pid, name=pid.upper(),
                            long_name=pid.upper(), description=None,
                        ),
                    ).name
                    for pid in parties
                    if pid not in claims_per_party
                ],
                available_claims=all_claims,
            )

        # =====================================================================
        # PHASE 2: Hierarchy Construction (single LLM call)
        # =====================================================================
        await self._send_thinking(
            session_id,
            "planning",
            "Strukturiere Vergleichspunkte...",
        )

        logger.info(
            f"Phase 2: Building hierarchy from {len(all_claims)} claims"
        )

        with debug_logger.timed_section("Phase 2: Hierarchy Construction"):
            start = time.monotonic()

            builder_output = await self._hierarchy_builder.execute(
                HierarchyBuilderInput(
                    query=query,
                    context_name=context_name,
                    parties=parties_info,
                    all_claims=all_claims,
                )
            )

            duration_ms = (time.monotonic() - start) * 1000

        # Build the ExplorationTree from the builder output
        root_node = ExplorationNode(**builder_output.tree_json)
        claims_lookup = {c.id: c for c in all_claims}

        exploration_tree = ExplorationTree(
            exploration_id=exploration_id,
            original_query=query,
            root=root_node,
            claims=claims_lookup,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Log hierarchy
        debug_logger.log_hierarchy_construction(
            tree=exploration_tree,
            total_claims=len(all_claims),
            party_count=len(parties_info),
            duration_ms=duration_ms,
        )

        # Send tree to frontend
        await self._send_exploration_tree(
            session_id, exploration_id, exploration_tree
        )

        # Count leaves for the ready event
        leaf_count = len(root_node.get_leaf_nodes())

        # Send ExplorationReadyEvent
        await self._sse.send_to_session(
            session_id,
            ExplorationReadyEvent(
                exploration_id=exploration_id,
                topics_count=len(root_node.children),
                subtopics_count=leaf_count,
                parties_count=len(parties_info),
            ),
        )

        logger.info(
            f"Exploration {exploration_id} complete: "
            f"{len(root_node.children)} top-level nodes, "
            f"{leaf_count} leaf nodes, "
            f"{len(all_claims)} claims"
        )

        # Flush debug log
        debug_logger.flush()

        return exploration_id, exploration_tree

    # =========================================================================
    # Phase 1: Claim Extraction
    # =========================================================================

    async def _phase1_claim_extraction(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        context_id: str,
        context_name: str,
        parties: list[str],
        parties_info: dict[str, PartyInfo],
        debug_logger: DebugLogger,
    ) -> tuple[list[Claim], dict[str, list[RetrievedChunk]]]:
        """
        Phase 1: RAG retrieval + claim extraction for each party in parallel.

        Returns:
            Tuple of (all_claims, party_chunks)
        """

        async def extract_for_party(
            party_id: str,
        ) -> tuple[str, PartyClaims | None, list[RetrievedChunk]]:
            try:
                party_info = parties_info.get(
                    party_id,
                    PartyInfo(
                        party_id=party_id,
                        name=party_id.upper(),
                        long_name=party_id.upper(),
                        description=None,
                    ),
                )

                # RAG retrieval
                rag_start = time.monotonic()
                chunks = await self._retrieve_chunks_for_party(
                    rag_query, context_id, party_id
                )
                rag_duration = (time.monotonic() - rag_start) * 1000

                debug_logger.log_rag_retrieval(
                    party_id=party_id,
                    party_name=party_info.name,
                    chunks=chunks,
                    duration_ms=rag_duration,
                )

                if not chunks:
                    logger.warning(f"No chunks for party {party_id}")
                    return party_id, None, []

                # Claim extraction
                extract_start = time.monotonic()
                result = await self._claim_extractor.execute(
                    ClaimExtractorInput(
                        query=query,
                        context_id=context_id,
                        context_name=context_name,
                        party_id=party_id,
                        party_info=party_info,
                        retrieved_chunks=chunks,
                    )
                )
                extract_duration = (time.monotonic() - extract_start) * 1000

                debug_logger.log_claim_extraction(
                    party_id=party_id,
                    party_name=party_info.name,
                    party_claims=result.party_claims,
                    duration_ms=extract_duration,
                )

                return party_id, result.party_claims, chunks

            except Exception as e:
                logger.error(
                    f"Claim extraction failed for party {party_id}: {e}"
                )
                return party_id, None, []

        # Run extraction for all parties in parallel with timeout
        tasks = [
            asyncio.wait_for(
                extract_for_party(party_id),
                timeout=PARTY_TIMEOUT_SECONDS,
            )
            for party_id in parties
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        all_claims: list[Claim] = []
        party_chunks: dict[str, list[RetrievedChunk]] = {}

        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"Phase 1 task failed: {type(result).__name__}: {result}")
                continue

            party_id, party_claims, chunks = result
            if party_claims is not None:
                all_claims.extend(party_claims.claims)
                party_chunks[party_id] = chunks

        return all_claims, party_chunks

    # =========================================================================
    # Context & Validation
    # =========================================================================

    async def _get_context_info(
        self,
        context_id: str,
        party_ids: list[str],
    ) -> tuple[str, dict[str, PartyInfo]]:
        """Fetch context name and party info from Firebase."""
        context = await aget_context_by_id(context_id)
        context_name = context.name if context else context_id

        all_parties = await aget_parties_for_context(context_id)
        all_parties_map = parties_to_info_map(all_parties)

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
        """Validate that enough parties have retrieved chunks."""
        total_parties = len(requested_parties)

        parties_with_chunks = [
            pid for pid in requested_parties if len(party_chunks.get(pid, [])) > 0
        ]
        count_with_chunks = len(parties_with_chunks)

        parties_without_chunks = [
            pid for pid in requested_parties if pid not in parties_with_chunks
        ]

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

        logger.info(
            f"Chunk coverage: {count_with_chunks}/{total_parties} parties have chunks"
        )
        if parties_without_chunks:
            logger.warning(
                f"Parties without chunks: {', '.join(parties_without_chunks)}"
            )

        min_parties_threshold = 2
        min_percentage_threshold = 0.5

        coverage_percentage = (
            count_with_chunks / total_parties if total_parties > 0 else 0
        )

        if (
            count_with_chunks < min_parties_threshold
            or coverage_percentage < min_percentage_threshold
        ):
            raise InsufficientChunksError(
                message=(
                    f"Insufficient document chunks: only {count_with_chunks} of "
                    f"{total_parties} parties have relevant content"
                ),
                total_parties=total_parties,
                parties_with_chunks=count_with_chunks,
                parties_without_chunks=party_names_without_chunks,
            )

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

    async def _send_exploration_tree(
        self,
        session_id: str,
        exploration_id: str,
        tree: ExplorationTree,
    ) -> None:
        """Send the exploration tree to the frontend."""
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
                tree=tree,
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
