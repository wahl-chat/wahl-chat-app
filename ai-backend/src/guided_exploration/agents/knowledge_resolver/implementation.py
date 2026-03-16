# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of party knowledge resolver agent."""

import logging
from typing import Callable, Awaitable
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.knowledge_resolver.interface import (
    PartyKnowledgeResolverInput,
    PartyKnowledgeResolverOutput,
)
from src.guided_exploration.agents.knowledge_resolver.prompts import (
    QUERY_REWRITE_SYSTEM_PROMPT,
    QUERY_REWRITE_USER_PROMPT,
    RESOLUTION_PROMPT,
    SYSTEM_PROMPT,
    LLMSubtopicKnowledge,
    PartyKnowledgeLLMOutput,
    QueryRewriteOutput,
    format_chunks,
    format_subtopics_list,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.exploration import (
    ExtractedClaim,
    ExtractedPosition,
    PartyKnowledge,
    PartySubtopicKnowledge,
    RetrievedChunk,
)

# Type alias for RAG retrieval function
RAGRetriever = Callable[[str, str, str], Awaitable[list[RetrievedChunk]]]

logger = logging.getLogger(__name__)


class PartyKnowledgeResolverAgent(
    BaseAgent[PartyKnowledgeResolverInput, PartyKnowledgeResolverOutput]
):
    """
    Resolves knowledge for a single party across all subtopics.

    Processes one party's documents to extract:
    - Positions on each subtopic
    - Key points from this party's perspective
    - Citations from this party's documents
    - Raw chunks for direct use in conversation

    Each party is processed independently, allowing parallel execution.
    Supports optional per-subtopic RAG retrieval with query rewriting.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        rag_retriever: RAGRetriever | None = None,
        fast_llm_provider: LLMProvider | None = None,
    ):
        self._llm = llm_provider
        self._rag_retriever = rag_retriever
        # Use fast LLM for query rewriting, fall back to main LLM
        self._fast_llm = fast_llm_provider or llm_provider

    @property
    def name(self) -> str:
        return "party_knowledge_resolver"

    async def execute(
        self, input: PartyKnowledgeResolverInput
    ) -> PartyKnowledgeResolverOutput:
        """
        Resolve knowledge for a single party across all subtopics using LLM.

        If a RAG retriever is provided, performs per-subtopic query rewriting
        and targeted retrieval. Otherwise uses the provided chunks.

        Stores both extracted claims and raw chunks for conversation use.
        """
        # Collect subtopics this party should cover
        subtopics_to_resolve = self._get_covered_subtopics(input)

        if not subtopics_to_resolve:
            # No subtopics to resolve - return empty knowledge
            return PartyKnowledgeResolverOutput(
                party_id=input.party_id,
                party_knowledge=PartyKnowledge(
                    party_id=input.party_id,
                    subtopics={},
                ),
            )

        # Get chunks - either use provided or do per-subtopic retrieval
        if self._rag_retriever:
            # Rewrite queries and retrieve targeted chunks per subtopic
            subtopic_chunks = await self._retrieve_targeted_chunks(
                input=input,
                subtopics=subtopics_to_resolve,
            )
            # Combine all chunks for the extraction step
            all_chunks = []
            for chunks in subtopic_chunks.values():
                all_chunks.extend(chunks)
            # Deduplicate by chunk_id
            seen_ids = set()
            party_chunks = []
            for chunk in all_chunks:
                if chunk.chunk_id not in seen_ids:
                    seen_ids.add(chunk.chunk_id)
                    party_chunks.append(chunk)
        else:
            # Use provided chunks
            party_chunks = [
                c for c in input.retrieved_chunks if c.party_id == input.party_id
            ]
            subtopic_chunks = {}

        # Format party description if available
        party_desc = (
            f"- Beschreibung: {input.party_info.description}"
            if input.party_info.description
            else ""
        )

        # Build system prompt with context and party info
        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
            party_id=input.party_id,
            party_name=input.party_info.name,
            party_long_name=input.party_info.long_name,
            party_description=party_desc,
        )

        # Format subtopics list
        subtopics_formatted = format_subtopics_list(subtopics_to_resolve)

        # Format chunks
        chunks_formatted = format_chunks(
            chunks=party_chunks,
            party_id=input.party_id,
        )

        # Build user prompt
        user_prompt = RESOLUTION_PROMPT.format(
            subtopics_list=subtopics_formatted,
            retrieved_chunks=chunks_formatted,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Use structured output for reliable parsing
        llm_output: PartyKnowledgeLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=PartyKnowledgeLLMOutput,
            temperature=0.2,  # Low temperature for factual extraction
        )

        # Convert LLM output to domain models (including chunks)
        subtopics_knowledge = self._convert_to_knowledge(
            llm_output=llm_output,
            party_id=input.party_id,
            all_subtopic_ids=[s[0] for s in subtopics_to_resolve],
            party_chunks=party_chunks,
            subtopic_chunks=subtopic_chunks,
        )

        return PartyKnowledgeResolverOutput(
            party_id=input.party_id,
            party_knowledge=PartyKnowledge(
                party_id=input.party_id,
                subtopics=subtopics_knowledge,
            ),
        )

    async def _retrieve_targeted_chunks(
        self,
        input: PartyKnowledgeResolverInput,
        subtopics: list[tuple[str, str, str, str]],
    ) -> dict[str, list[RetrievedChunk]]:
        """
        Rewrite queries and retrieve targeted chunks for each subtopic.

        Returns mapping of subtopic_id to retrieved chunks.
        """
        if not self._rag_retriever:
            return {}

        # Step 1: Rewrite queries for all subtopics
        subtopics_formatted = format_subtopics_list(subtopics)
        user_prompt = QUERY_REWRITE_USER_PROMPT.format(
            subtopics_list=subtopics_formatted,
        )

        messages = [
            SystemMessage(content=QUERY_REWRITE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        # Use fast LLM for query rewriting (simple task)
        rewrite_output: QueryRewriteOutput = await self._fast_llm.generate_structured(
            messages=messages,
            output_schema=QueryRewriteOutput,
            temperature=0.0,
        )

        # Build query map
        query_map = {q.subtopic_id: q.rag_query for q in rewrite_output.queries}

        logger.info(
            f"Rewritten queries for {input.party_id}: "
            f"{list(query_map.values())[:3]}..."
        )

        # Step 2: Retrieve chunks for each subtopic
        subtopic_chunks: dict[str, list[RetrievedChunk]] = {}

        for subtopic_id, name, description, scope in subtopics:
            # Get rewritten query or fall back to subtopic name + description
            query = query_map.get(subtopic_id, f"{name} {description}")

            chunks = await self._rag_retriever(
                query,
                input.context_id,
                input.party_id,
            )

            subtopic_chunks[subtopic_id] = chunks
            logger.debug(
                f"Retrieved {len(chunks)} chunks for {input.party_id}/{subtopic_id}"
            )

        return subtopic_chunks

    def _get_covered_subtopics(
        self,
        input: PartyKnowledgeResolverInput,
    ) -> list[tuple[str, str, str, str]]:
        """Get list of subtopics this party should cover.

        Returns list of (subtopic_id, name, description, scope) tuples.
        """
        subtopics = []

        for topic in input.topic_tree.topics:
            for subtopic in topic.subtopics:
                # Check if this party covers this subtopic
                covering_parties = input.party_coverage.get(subtopic.id, [])
                party_covers = (
                    input.party_id in covering_parties
                    or input.party_id in subtopic.parties
                )

                if party_covers:
                    # Get scope with fallback to empty string
                    scope = getattr(subtopic, "scope", "") or ""
                    subtopics.append(
                        (subtopic.id, subtopic.name, subtopic.description, scope)
                    )

        return subtopics

    def _convert_to_knowledge(
        self,
        llm_output: PartyKnowledgeLLMOutput,
        party_id: str,
        all_subtopic_ids: list[str],
        party_chunks: list[RetrievedChunk],
        subtopic_chunks: dict[str, list[RetrievedChunk]] | None = None,
    ) -> dict[str, PartySubtopicKnowledge]:
        """Convert LLM output to PartySubtopicKnowledge domain models."""
        knowledge_map: dict[str, PartySubtopicKnowledge] = {}
        subtopic_chunks = subtopic_chunks or {}

        # Create a lookup from LLM output
        llm_knowledge_by_id = {k.subtopic_id: k for k in llm_output.subtopics}

        for subtopic_id in all_subtopic_ids:
            llm_knowledge = llm_knowledge_by_id.get(subtopic_id)

            # Get chunks for this subtopic (targeted or from LLM indices)
            if subtopic_id in subtopic_chunks:
                # Use targeted chunks from per-subtopic retrieval
                chunks_for_subtopic = subtopic_chunks[subtopic_id]
            elif llm_knowledge and llm_knowledge.relevant_chunk_indices:
                # Use indices from LLM output
                chunks_for_subtopic = [
                    party_chunks[i - 1]
                    for i in llm_knowledge.relevant_chunk_indices
                    if 0 < i <= len(party_chunks)
                ]
            else:
                chunks_for_subtopic = []

            if llm_knowledge and llm_knowledge.has_content and llm_knowledge.claims:
                knowledge_map[subtopic_id] = self._convert_subtopic_knowledge(
                    llm_knowledge=llm_knowledge,
                    party_id=party_id,
                    party_chunks=party_chunks,
                    chunks_for_subtopic=chunks_for_subtopic,
                )
            else:
                # No content found - but still include any retrieved chunks
                knowledge_map[subtopic_id] = PartySubtopicKnowledge(
                    subtopic_id=subtopic_id,
                    party_id=party_id,
                    position=None,
                    key_points=[],
                    citations=[],
                    retrieved_chunks=chunks_for_subtopic,
                )

        return knowledge_map

    def _convert_subtopic_knowledge(
        self,
        llm_knowledge: LLMSubtopicKnowledge,
        party_id: str,
        party_chunks: list[RetrievedChunk],
        chunks_for_subtopic: list[RetrievedChunk] | None = None,
    ) -> PartySubtopicKnowledge:
        """Convert a single LLM subtopic knowledge to domain model."""
        chunks_for_subtopic = chunks_for_subtopic or []

        if not llm_knowledge.has_content or not llm_knowledge.claims:
            return PartySubtopicKnowledge(
                subtopic_id=llm_knowledge.subtopic_id,
                party_id=party_id,
                position=None,
                key_points=[],
                citations=[],
                retrieved_chunks=chunks_for_subtopic,
            )

        # Convert claims and create citations from them
        claims: list[ExtractedClaim] = []
        citations: list[Citation] = []
        key_points: list[str] = []

        for llm_claim in llm_knowledge.claims:
            # Look up chunk metadata by index (1-based from LLM, convert to 0-based)
            chunk_idx = llm_claim.chunk_index - 1
            if 0 <= chunk_idx < len(party_chunks):
                chunk = party_chunks[chunk_idx]
                # Use document_name from metadata if available
                source_doc = chunk.metadata.get("document_name", chunk.source_document)
                source_page = chunk.source_page
                source_section = chunk.source_section
                # Additional metadata for Citation
                document_publish_date = chunk.metadata.get("document_publish_date")
                url = chunk.metadata.get("url")
            else:
                # Fallback if chunk index is invalid
                logger.warning(
                    f"Invalid chunk_index {llm_claim.chunk_index} "
                    f"(max: {len(party_chunks)}) for claim: {llm_claim.claim[:50]}"
                )
                source_doc = "Unbekannt"
                source_page = None
                source_section = None
                document_publish_date = None
                url = None

            # Generate citation ID
            citation_id = f"{party_id}-{llm_knowledge.subtopic_id}-{uuid4().hex[:8]}"

            # Create extracted claim with linked citation ID
            claims.append(
                ExtractedClaim(
                    claim=llm_claim.claim,
                    quote=llm_claim.quote,
                    source_doc=source_doc,
                    source_page=source_page,
                    claim_type=llm_claim.claim_type,
                    citation_id=citation_id,
                )
            )

            # Create citation for each claim with full metadata
            citations.append(
                Citation(
                    id=citation_id,
                    party=party_id,
                    document=source_doc,
                    section=source_section,
                    page=source_page + 1 if source_page is not None else None,
                    document_publish_date=document_publish_date,
                    url=url,
                )
            )

            # Add to key points (first 5 claims)
            if len(key_points) < 5:
                key_points.append(llm_claim.claim)

        # Build extracted position
        position = ExtractedPosition(
            party_id=party_id,
            summary=llm_knowledge.summary or "",
            claims=claims,
        )

        return PartySubtopicKnowledge(
            subtopic_id=llm_knowledge.subtopic_id,
            party_id=party_id,
            position=position,
            key_points=key_points,
            citations=citations,
            retrieved_chunks=chunks_for_subtopic,
        )
