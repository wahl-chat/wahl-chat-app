# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Service to merge per-party knowledge into a unified KnowledgeBase."""

from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.exploration import (
    ExtractedPosition,
    KnowledgeBase,
    PartyKnowledge,
    ResolvedKnowledge,
    RetrievedChunk,
)
from src.guided_exploration.models.tree import TopicTree


def merge_party_knowledge(
    topic_tree: TopicTree,
    party_knowledge: dict[str, PartyKnowledge],
) -> KnowledgeBase:
    """
    Merge per-party knowledge into a unified KnowledgeBase.

    Takes the knowledge resolved for each party and combines it into
    a single KnowledgeBase with ResolvedKnowledge per leaf node.
    Leaf nodes can be either subtopics or topics without subtopics.

    Args:
        topic_tree: The combined topic tree
        party_knowledge: Mapping of party_id to PartyKnowledge

    Returns:
        A unified KnowledgeBase with all party positions merged
    """
    leaves: dict[str, ResolvedKnowledge] = {}

    for topic in topic_tree.topics:
        if topic.subtopics:
            # Topic has subtopics - create knowledge for each subtopic
            for subtopic in topic.subtopics:
                resolved = _merge_leaf_knowledge(
                    leaf_id=subtopic.id,
                    leaf_name=subtopic.name,
                    party_knowledge=party_knowledge,
                )
                leaves[subtopic.id] = resolved
        else:
            # Topic is a leaf (no subtopics) - create knowledge for the topic itself
            resolved = _merge_leaf_knowledge(
                leaf_id=topic.id,
                leaf_name=topic.name,
                party_knowledge=party_knowledge,
            )
            leaves[topic.id] = resolved

    return KnowledgeBase(subtopics=leaves)


def _merge_leaf_knowledge(
    leaf_id: str,
    leaf_name: str,
    party_knowledge: dict[str, PartyKnowledge],
) -> ResolvedKnowledge:
    """Merge knowledge from all parties for a single leaf node (subtopic or leaf topic)."""
    party_positions: dict[str, ExtractedPosition] = {}
    all_citations: list[Citation] = []
    party_chunks: dict[str, list[RetrievedChunk]] = {}

    for party_id, pk in party_knowledge.items():
        # Try to get knowledge for this leaf (works for both subtopics and leaf topics)
        leaf_knowledge = pk.get_for_subtopic(leaf_id)
        if leaf_knowledge is None:
            continue

        # Add party position if available
        if leaf_knowledge.position is not None:
            party_positions[party_id] = leaf_knowledge.position

        # Collect citations
        all_citations.extend(leaf_knowledge.citations)

        # Collect chunks per party
        if leaf_knowledge.retrieved_chunks:
            party_chunks[party_id] = leaf_knowledge.retrieved_chunks

    return ResolvedKnowledge(
        leaf_id=leaf_id,
        party_positions=party_positions,
        citation_pool=all_citations,
        party_chunks=party_chunks,
    )
