# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of hierarchy builder agent."""

import logging
from collections import defaultdict

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.hierarchy_builder.interface import (
    HierarchyBuilderInput,
    HierarchyBuilderOutput,
)
from src.guided_exploration.agents.hierarchy_builder.prompts import (
    CONSTRUCTION_PROMPT,
    STUDY_MODE_BLOCK,
    STUDY_MODE_BLOCK_EMPTY,
    STUDY_MODE_REMINDER,
    STUDY_MODE_REMINDER_EMPTY,
    SYSTEM_PROMPT,
    HierarchyBuilderLLMOutput,
    LLMHierarchyNode,
    format_positions_for_prompt,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_context import format_party_context_for_prompt
from src.guided_exploration.models.position import Position
from src.guided_exploration.models.tree import ExplorationNode, NodeStatus

logger = logging.getLogger(__name__)


class HierarchyBuilderAgent(BaseAgent[HierarchyBuilderInput, HierarchyBuilderOutput]):
    """
    Builds a navigable hierarchy from concrete party positions.

    Takes all positions from all parties and organizes them into a multi-level
    tree structure. The decomposition is adaptive — the LLM chooses the best
    structure (thematic, policy-type, or hybrid) based on the actual content.

    Key difference from TopicCombinerAgent: works with concrete positions
    (bottom-up) rather than abstract topic trees (top-down merging).
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "hierarchy_builder"

    async def execute(self, input: HierarchyBuilderInput) -> HierarchyBuilderOutput:
        """
        Build a hierarchical tree from all party positions.
        """
        formatted_positions = format_positions_for_prompt(input.all_positions, input.parties)
        party_context = format_party_context_for_prompt(
            parties=input.parties,
            context_name=input.context_name,
        )

        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
            party_context=party_context,
            study_mode_block=STUDY_MODE_BLOCK if input.is_study else STUDY_MODE_BLOCK_EMPTY,
        )

        user_prompt = CONSTRUCTION_PROMPT.format(
            query=input.query,
            position_count=len(input.all_positions),
            formatted_positions=formatted_positions,
            study_mode_reminder=STUDY_MODE_REMINDER if input.is_study else STUDY_MODE_REMINDER_EMPTY,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        llm_output: HierarchyBuilderLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=HierarchyBuilderLLMOutput,
            temperature=0.3,
        )

        # Convert LLM output to ExplorationNode tree
        root_children, position_assignment = self._convert_to_nodes(
            llm_output, input.all_positions
        )

        # Build the root node (wraps top-level nodes)
        all_party_ids = list({p.party_id for p in input.all_positions})
        root = ExplorationNode(
            id="root",
            name=input.query,
            description=f"Vergleich der Parteipositionen zu: {input.query}",
            children=root_children,
            party_ids=sorted(all_party_ids),
        )

        logger.info(
            f"Built hierarchy: {len(root_children)} top-level nodes, "
            f"{len(position_assignment)} leaf nodes with positions"
        )

        return HierarchyBuilderOutput(
            tree_json=root.model_dump(),
            position_assignment=position_assignment,
        )

    def _convert_to_nodes(
        self,
        llm_output: HierarchyBuilderLLMOutput,
        all_positions: list[Position],
    ) -> tuple[list[ExplorationNode], dict[str, list[str]]]:
        """
        Convert LLM hierarchy nodes to ExplorationNode tree.

        Returns:
            Tuple of (children nodes, position_assignment mapping)
        """
        position_assignment: dict[str, list[str]] = {}
        children = []

        for llm_node in llm_output.nodes:
            node = self._convert_node(
                llm_node, all_positions, position_assignment, parent_id=""
            )
            children.append(node)

        return children, position_assignment

    def _convert_node(
        self,
        llm_node: LLMHierarchyNode,
        all_positions: list[Position],
        position_assignment: dict[str, list[str]],
        parent_id: str,
    ) -> ExplorationNode:
        """Recursively convert a single LLM node to ExplorationNode."""
        node_id = f"{parent_id}.{llm_node.id}" if parent_id else llm_node.id

        # Convert children recursively
        children = [
            self._convert_node(child, all_positions, position_assignment, parent_id=node_id)
            for child in llm_node.children
        ]

        # For leaf nodes: resolve position_indices to position_ids
        position_ids: list[str] = []
        party_ids_set: set[str] = set()

        if not children and llm_node.position_indices:
            # This is a leaf node
            for idx in llm_node.position_indices:
                if 0 <= idx < len(all_positions):
                    position = all_positions[idx]
                    position_ids.append(position.id)
                    party_ids_set.add(position.party_id)
                else:
                    logger.warning(
                        f"Position index {idx} out of range for node {node_id}"
                    )

            position_assignment[node_id] = position_ids
        elif children:
            # Branch node: aggregate party_ids from children
            for child in children:
                party_ids_set.update(child.party_ids)

        return ExplorationNode(
            id=node_id,
            name=llm_node.name,
            description=llm_node.description,
            children=children,
            party_ids=sorted(party_ids_set),
            position_ids=position_ids,
            status=NodeStatus.PENDING,
        )
