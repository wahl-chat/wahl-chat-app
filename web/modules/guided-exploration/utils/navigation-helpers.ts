/**
 * Navigation Helper Utilities
 * Functions for working with navigation paths and breadcrumbs
 */

import type {
  BreadcrumbItem,
  ExplorationTree,
} from '@/modules/guided-exploration/types';
import { findNode, getPathTo, isLeaf } from './tree-helpers';

/**
 * Get the parent path (one level up)
 */
export function getParentPath(path: string[]): string[] {
  return path.slice(0, -1);
}

/**
 * Check if we're at the root level
 */
export function isAtRoot(path: string[]): boolean {
  return path.length === 0;
}

/**
 * Build breadcrumb items from a path and tree
 */
export function buildBreadcrumb(
  tree: ExplorationTree,
  path: string[],
): BreadcrumbItem[] {
  const items: BreadcrumbItem[] = [
    { id: 'root', name: 'Übersicht', level: 'root' },
  ];

  if (path.length === 0) return items;

  // Use the last element of path as the target node
  const targetId = path[path.length - 1];
  const nodePath = getPathTo(tree, targetId);

  if (nodePath) {
    // Skip root node (index 0), add rest as breadcrumb items
    for (let i = 1; i < nodePath.length; i++) {
      const node = nodePath[i];
      items.push({
        id: node.id,
        name: node.name,
        level: isLeaf(node) ? 'subtopic' : 'topic',
      });
    }
  }

  return items;
}

/**
 * Get sibling navigation info for a node
 */
export function getSiblingNavigation(
  tree: ExplorationTree,
  nodeId: string,
): {
  previous?: { id: string; name: string };
  next?: { id: string; name: string };
} {
  // Find the parent of this node by looking at path
  const nodePath = getPathTo(tree, nodeId);
  if (!nodePath || nodePath.length < 2) return {};

  const parent = nodePath[nodePath.length - 2];
  const index = parent.children.findIndex((c) => c.id === nodeId);

  const previous =
    index > 0
      ? {
          id: parent.children[index - 1].id,
          name: parent.children[index - 1].name,
        }
      : undefined;

  const next =
    index < parent.children.length - 1
      ? {
          id: parent.children[index + 1].id,
          name: parent.children[index + 1].name,
        }
      : undefined;

  return { previous, next };
}

/**
 * Determine the view type from a node ID
 */
export function getViewFromNodeId(
  tree: ExplorationTree,
  nodeId: string | null,
): 'root' | 'branch' | 'leaf' {
  if (!nodeId) return 'root';

  const node = findNode(tree, nodeId);
  if (!node) return 'root';

  return isLeaf(node) ? 'leaf' : 'branch';
}

/**
 * Check if a node ID is valid in the tree
 */
export function isValidNodeId(tree: ExplorationTree, nodeId: string): boolean {
  return findNode(tree, nodeId) !== undefined;
}

/**
 * Get the display name for a node
 */
export function getNodeDisplayName(
  tree: ExplorationTree,
  nodeId: string | null,
): string {
  if (!nodeId) return 'Übersicht';

  const node = findNode(tree, nodeId);
  return node?.name ?? nodeId;
}
