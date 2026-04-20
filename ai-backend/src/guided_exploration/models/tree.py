# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for the exploration tree structure — position-based adaptive hierarchy."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.guided_exploration.models.position import Position


class NodeStatus(StrEnum):
    """Status of an exploration node. String values match the wire format."""

    PENDING = "pending"
    LOADED = "loaded"
    STARTED = "started"
    EXPLORED = "explored"


class ExplorationNode(BaseModel):
    """
    Recursive node in the exploration tree.

    Can be a branch (has children) or a leaf (has position_ids, no children).
    The tree adapts its depth to the content — typically 2-3 levels.
    Screen reader users navigate this tree, so names must be descriptive.
    """

    id: str = Field(..., description="Unique node ID, e.g., 'energie.erneuerbare'")
    name: str = Field(
        ...,
        description=(
            "Descriptive display name. Must be understandable on its own for "
            "screen reader users, e.g., 'Erneuerbare Energien'"
        ),
    )
    description: str = Field(
        ..., description="Brief description of what this node covers (1-2 sentences)"
    )
    children: list[ExplorationNode] = Field(
        default_factory=list,
        description="Child nodes. Empty list means this is a leaf node.",
    )
    party_ids: list[str] = Field(
        default_factory=list,
        description="Party IDs that have positions in this node or its descendants",
    )
    position_ids: list[str] = Field(
        default_factory=list,
        description="Position IDs assigned to this leaf node. Empty for branch nodes.",
    )
    status: NodeStatus = Field(
        default=NodeStatus.PENDING,
        description=(
            "Exploration status: 'pending' (no content yet), 'loaded' (content "
            "pre-generated but user hasn't opened), 'started' (user has opened), "
            "'explored' (user marked as done)."
        ),
    )

    @property
    def is_leaf(self) -> bool:
        """Whether this is a leaf node (no children)."""
        return len(self.children) == 0

    def find_node(self, node_id: str) -> ExplorationNode | None:
        """Find a node by ID in this subtree."""
        if self.id == node_id:
            return self
        for child in self.children:
            found = child.find_node(node_id)
            if found:
                return found
        return None

    def get_leaf_nodes(self) -> list[ExplorationNode]:
        """Get all leaf nodes in this subtree."""
        if self.is_leaf:
            return [self]
        leaves = []
        for child in self.children:
            leaves.extend(child.get_leaf_nodes())
        return leaves

    def get_path_to(self, node_id: str) -> list[ExplorationNode] | None:
        """Get the path from this node to a target node (inclusive)."""
        if self.id == node_id:
            return [self]
        for child in self.children:
            path = child.get_path_to(node_id)
            if path is not None:
                return [self] + path
        return None


class ExplorationTree(BaseModel):
    """
    Complete exploration tree with position-based hierarchy.

    The tree structure emerges bottom-up from concrete party positions.
    Positions are extracted first, then organized into a navigable hierarchy.
    """

    exploration_id: str = Field(..., description="ID of the parent exploration")
    original_query: str = Field(
        ..., description="The user's original query that generated this tree"
    )
    selected_directions: list[str] = Field(
        default_factory=list,
        description="User-selected direction focuses from topic direction choice",
    )
    root: ExplorationNode = Field(
        ..., description="Root node of the exploration tree"
    )
    positions: dict[str, Position] = Field(
        default_factory=dict,
        description="Lookup table: position_id -> Position. All positions referenced by leaf nodes.",
    )
    created_at: datetime = Field(..., description="When the tree was created")
    updated_at: datetime = Field(..., description="When the tree was last updated")

    def find_node(self, node_id: str) -> ExplorationNode | None:
        """Find any node in the tree by ID."""
        return self.root.find_node(node_id)

    def get_positions_for_leaf(self, leaf_id: str) -> list[Position]:
        """Get all positions for a leaf node."""
        node = self.find_node(leaf_id)
        if node is None or not node.is_leaf:
            return []
        return [self.positions[pid] for pid in node.position_ids if pid in self.positions]

    def get_positions_by_party(self, leaf_id: str) -> dict[str, list[Position]]:
        """Get positions for a leaf grouped by party."""
        positions = self.get_positions_for_leaf(leaf_id)
        by_party: dict[str, list[Position]] = {}
        for position in positions:
            by_party.setdefault(position.party_id, []).append(position)
        return by_party
