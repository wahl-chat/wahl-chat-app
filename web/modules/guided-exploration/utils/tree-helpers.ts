/**
 * Tree Helper Utilities
 * Functions for working with the topic tree structure
 */

import type {
  Subtopic,
  Topic,
  TopicTree,
} from '@/modules/guided-exploration/types';

/**
 * Find a topic by ID
 */
export function findTopic(tree: TopicTree, topicId: string): Topic | undefined {
  return tree.topics.find((t) => t.id === topicId);
}

/**
 * Find a subtopic by ID (format: "topicId.subtopicId" or just "subtopicId")
 */
export function findSubtopic(
  tree: TopicTree,
  subtopicId: string,
): { topic: Topic; subtopic: Subtopic } | undefined {
  // Check if it's a compound ID
  if (subtopicId.includes('.')) {
    const [topicId, subId] = subtopicId.split('.');
    const topic = findTopic(tree, topicId);
    if (topic) {
      const subtopic = topic.subtopics.find(
        (s) => s.id === subtopicId || s.id === subId,
      );
      if (subtopic) {
        return { topic, subtopic };
      }
    }
  }

  // Search all topics
  for (const topic of tree.topics) {
    const subtopic = topic.subtopics.find(
      (s) => s.id === subtopicId || s.id.endsWith(`.${subtopicId}`),
    );
    if (subtopic) {
      return { topic, subtopic };
    }
  }

  return undefined;
}

/**
 * Get all leaves (subtopics) in the tree
 */
export function getAllLeaves(tree: TopicTree): Subtopic[] {
  return tree.topics.flatMap((topic) => topic.subtopics);
}

/**
 * Get leaves for a specific topic
 */
export function getTopicLeaves(tree: TopicTree, topicId: string): Subtopic[] {
  const topic = findTopic(tree, topicId);
  return topic?.subtopics ?? [];
}

/**
 * Count total leaves in tree
 */
export function countLeaves(tree: TopicTree): number {
  return tree.topics.reduce((acc, topic) => acc + topic.subtopics.length, 0);
}

/**
 * Count explored leaves in tree
 */
export function countExploredLeaves(tree: TopicTree): number {
  return tree.topics.reduce(
    (acc, topic) =>
      acc + topic.subtopics.filter((s) => s.status === 'explored').length,
    0,
  );
}

/**
 * Get exploration progress for a topic
 */
export function getTopicProgress(
  tree: TopicTree,
  topicId: string,
): { explored: number; total: number } {
  const topic = findTopic(tree, topicId);
  if (!topic) {
    return { explored: 0, total: 0 };
  }

  const explored = topic.subtopics.filter(
    (s) => s.status === 'explored',
  ).length;
  return { explored, total: topic.subtopics.length };
}

/**
 * Get overall exploration progress
 */
export function getOverallProgress(tree: TopicTree): {
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
 * Check if a topic has any explored subtopics
 */
export function hasExploredSubtopics(
  tree: TopicTree,
  topicId: string,
): boolean {
  const topic = findTopic(tree, topicId);
  return topic?.subtopics.some((s) => s.status === 'explored') ?? false;
}

/**
 * Check if all subtopics in a topic are explored
 */
export function isTopicFullyExplored(
  tree: TopicTree,
  topicId: string,
): boolean {
  const topic = findTopic(tree, topicId);
  if (!topic || topic.subtopics.length === 0) {
    return false;
  }
  return topic.subtopics.every((s) => s.status === 'explored');
}

/**
 * Get the next unexplored leaf in the tree
 */
export function getNextUnexploredLeaf(
  tree: TopicTree,
  currentLeafId?: string,
): Subtopic | undefined {
  const allLeaves = getAllLeaves(tree);
  const currentIndex = currentLeafId
    ? allLeaves.findIndex((l) => l.id === currentLeafId)
    : -1;

  // Search from current position forward
  for (let i = currentIndex + 1; i < allLeaves.length; i++) {
    if (allLeaves[i].status === 'pending') {
      return allLeaves[i];
    }
  }

  // Wrap around and search from beginning
  for (let i = 0; i <= currentIndex; i++) {
    if (allLeaves[i].status === 'pending') {
      return allLeaves[i];
    }
  }

  return undefined;
}

/**
 * Get parties that have positions on a specific subtopic
 */
export function getSubtopicParties(
  tree: TopicTree,
  subtopicId: string,
): string[] {
  const result = findSubtopic(tree, subtopicId);
  return result?.subtopic.parties ?? [];
}

/**
 * Get all unique parties across the entire tree
 */
export function getAllParties(tree: TopicTree): string[] {
  const parties = new Set<string>();

  for (const topic of tree.topics) {
    for (const subtopic of topic.subtopics) {
      for (const party of subtopic.parties) {
        parties.add(party);
      }
    }
  }

  return Array.from(parties).sort();
}
