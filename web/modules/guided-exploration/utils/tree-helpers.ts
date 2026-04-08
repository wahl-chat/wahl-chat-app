/**
 * Tree Helper Utilities
 * Functions for working with the ExplorationTree structure
 */

import type {
  ExplorationNode,
  ExplorationTree,
  Position,
} from '@/modules/guided-exploration/types';

/**
 * Find a node by ID anywhere in the tree
 */
export function findNode(
  tree: ExplorationTree,
  nodeId: string,
): ExplorationNode | undefined {
  return findNodeRecursive(tree.root, nodeId);
}

function findNodeRecursive(
  node: ExplorationNode,
  nodeId: string,
): ExplorationNode | undefined {
  if (node.id === nodeId) return node;
  for (const child of node.children) {
    const found = findNodeRecursive(child, nodeId);
    if (found) return found;
  }
  return undefined;
}

/**
 * Get the path from root to a node (inclusive)
 */
export function getPathTo(
  tree: ExplorationTree,
  nodeId: string,
): ExplorationNode[] | undefined {
  return getPathRecursive(tree.root, nodeId);
}

function getPathRecursive(
  node: ExplorationNode,
  nodeId: string,
): ExplorationNode[] | undefined {
  if (node.id === nodeId) return [node];
  for (const child of node.children) {
    const path = getPathRecursive(child, nodeId);
    if (path) return [node, ...path];
  }
  return undefined;
}

/**
 * Check if a node is a leaf (no children)
 */
export function isLeaf(node: ExplorationNode): boolean {
  return node.children.length === 0;
}

/**
 * Get all leaf nodes in the tree
 */
export function getAllLeaves(tree: ExplorationTree): ExplorationNode[] {
  return getLeavesRecursive(tree.root);
}

function getLeavesRecursive(node: ExplorationNode): ExplorationNode[] {
  if (isLeaf(node)) return [node];
  return node.children.flatMap(getLeavesRecursive);
}

/**
 * Get leaf nodes under a specific branch
 */
export function getBranchLeaves(node: ExplorationNode): ExplorationNode[] {
  return getLeavesRecursive(node);
}

/**
 * Count total leaves in tree
 */
export function countLeaves(tree: ExplorationTree): number {
  return getAllLeaves(tree).length;
}

/**
 * Count explored leaves in tree
 */
export function countExploredLeaves(tree: ExplorationTree): number {
  return getAllLeaves(tree).filter((l) => l.status === 'explored').length;
}

/**
 * Get exploration progress for a branch node
 */
export function getBranchProgress(node: ExplorationNode): {
  explored: number;
  total: number;
} {
  const leaves = getBranchLeaves(node);
  const explored = leaves.filter((l) => l.status === 'explored').length;
  return { explored, total: leaves.length };
}

/**
 * Get overall exploration progress
 */
export function getOverallProgress(tree: ExplorationTree): {
  explored: number;
  total: number;
  percentage: number;
} {
  const total = countLeaves(tree);
  const explored = countExploredLeaves(tree);
  const percentage = total > 0 ? Math.round((explored / total) * 100) : 0;
  return { explored, total, percentage };
}

/**
 * Check if a branch has any explored leaves
 */
export function hasExploredLeaves(node: ExplorationNode): boolean {
  return getBranchLeaves(node).some((l) => l.status === 'explored');
}

/**
 * Check if all leaves under a branch are explored
 */
export function isFullyExplored(node: ExplorationNode): boolean {
  const leaves = getBranchLeaves(node);
  return leaves.length > 0 && leaves.every((l) => l.status === 'explored');
}

/**
 * Get the next unexplored leaf in the tree
 */
export function getNextUnexploredLeaf(
  tree: ExplorationTree,
  currentLeafId?: string,
): ExplorationNode | undefined {
  const allLeaves = getAllLeaves(tree);
  const currentIndex = currentLeafId
    ? allLeaves.findIndex((l) => l.id === currentLeafId)
    : -1;

  // Search forward from current
  for (let i = currentIndex + 1; i < allLeaves.length; i++) {
    if (allLeaves[i].status === 'pending') return allLeaves[i];
  }

  // Wrap around
  for (let i = 0; i <= currentIndex; i++) {
    if (allLeaves[i].status === 'pending') return allLeaves[i];
  }

  return undefined;
}

/**
 * Get positions for a leaf node
 */
export function getPositionsForLeaf(
  tree: ExplorationTree,
  leafId: string,
): Position[] {
  const node = findNode(tree, leafId);
  if (!node || !isLeaf(node)) return [];
  return node.positionIds
    .map((id) => tree.positions[id])
    .filter((c): c is Position => c !== undefined);
}

/**
 * Get positions for a leaf grouped by party
 */
export function getPositionsByParty(
  tree: ExplorationTree,
  leafId: string,
): Record<string, Position[]> {
  const positions = getPositionsForLeaf(tree, leafId);
  const byParty: Record<string, Position[]> = {};
  for (const position of positions) {
    if (!byParty[position.partyId]) byParty[position.partyId] = [];
    byParty[position.partyId].push(position);
  }
  return byParty;
}

/**
 * Get all unique parties across the entire tree
 */
export function getAllParties(tree: ExplorationTree): string[] {
  const parties = new Set<string>();
  for (const position of Object.values(tree.positions)) {
    parties.add(position.partyId);
  }
  return Array.from(parties).sort();
}
