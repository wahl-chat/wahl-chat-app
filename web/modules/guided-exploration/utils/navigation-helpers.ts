/**
 * Navigation Helper Utilities
 * Functions for working with navigation paths and breadcrumbs
 */

import type {
  BreadcrumbItem,
  TopicTree,
} from '@/modules/guided-exploration/types';
import { findSubtopic, findTopic } from './tree-helpers';

/**
 * Build a path array from a leaf ID
 * e.g., "housing.rent-control" -> ["housing", "rent-control"]
 */
export function pathFromLeafId(leafId: string): string[] {
  return leafId.split('.');
}

/**
 * Build a leaf ID from a path
 * e.g., ["housing", "rent-control"] -> "housing.rent-control"
 */
export function leafIdFromPath(path: string[]): string {
  return path.join('.');
}

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
 * Check if we're at a topic (branch) level
 */
export function isAtTopic(path: string[]): boolean {
  return path.length === 1;
}

/**
 * Check if we're at a subtopic (leaf) level
 */
export function isAtSubtopic(path: string[]): boolean {
  return path.length === 2;
}

/**
 * Get the current topic ID from path (if any)
 */
export function getCurrentTopicId(path: string[]): string | null {
  return path.length > 0 ? path[0] : null;
}

/**
 * Get the current subtopic ID from path (if any)
 */
export function getCurrentSubtopicId(path: string[]): string | null {
  return path.length === 2 ? leafIdFromPath(path) : null;
}

/**
 * Build breadcrumb items from a path and tree
 */
export function buildBreadcrumb(
  tree: TopicTree,
  path: string[],
): BreadcrumbItem[] {
  const items: BreadcrumbItem[] = [
    { id: 'root', name: 'Übersicht', level: 'root' },
  ];

  if (path.length >= 1) {
    const topic = findTopic(tree, path[0]);
    if (topic) {
      items.push({ id: topic.id, name: topic.name, level: 'topic' });
    }
  }

  if (path.length === 2) {
    const result = findSubtopic(tree, leafIdFromPath(path));
    if (result) {
      items.push({
        id: result.subtopic.id,
        name: result.subtopic.name,
        level: 'subtopic',
      });
    }
  }

  return items;
}

/**
 * Get sibling navigation info for a leaf
 */
export function getSiblingNavigation(
  tree: TopicTree,
  leafId: string,
): {
  previous?: { id: string; name: string };
  next?: { id: string; name: string };
} {
  const result = findSubtopic(tree, leafId);
  if (!result) {
    return {};
  }

  const { topic, subtopic } = result;
  const index = topic.subtopics.findIndex((s) => s.id === subtopic.id);

  const previous =
    index > 0
      ? {
          id: topic.subtopics[index - 1].id,
          name: topic.subtopics[index - 1].name,
        }
      : undefined;

  const next =
    index < topic.subtopics.length - 1
      ? {
          id: topic.subtopics[index + 1].id,
          name: topic.subtopics[index + 1].name,
        }
      : undefined;

  return { previous, next };
}

/**
 * Determine the view type from a path
 * If tree is provided, checks if a topic at path[0] is a leaf topic (no subtopics)
 */
export function getViewFromPath(
  path: string[],
  tree?: TopicTree,
): 'root' | 'branch' | 'leaf' {
  if (path.length === 0) return 'root';
  if (path.length === 1) {
    // Check if this topic is a leaf (has no subtopics)
    if (tree) {
      const topic = findTopic(tree, path[0]);
      if (topic && topic.subtopics.length === 0) {
        return 'leaf';
      }
    }
    return 'branch';
  }
  return 'leaf';
}

/**
 * Check if a path is valid for a given tree
 */
export function isValidPath(tree: TopicTree, path: string[]): boolean {
  if (path.length === 0) return true;

  const topic = findTopic(tree, path[0]);
  if (!topic) return false;

  if (path.length === 1) return true;

  if (path.length === 2) {
    return topic.subtopics.some(
      (s) => s.id === leafIdFromPath(path) || s.id.endsWith(`.${path[1]}`),
    );
  }

  return false;
}

/**
 * Get the display name for a path
 */
export function getPathDisplayName(tree: TopicTree, path: string[]): string {
  if (path.length === 0) return 'Übersicht';

  if (path.length === 1) {
    const topic = findTopic(tree, path[0]);
    return topic?.name ?? path[0];
  }

  if (path.length === 2) {
    const result = findSubtopic(tree, leafIdFromPath(path));
    return result?.subtopic.name ?? path[1];
  }

  return path.join(' > ');
}
