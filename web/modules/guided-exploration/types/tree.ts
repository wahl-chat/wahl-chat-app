/**
 * Topic Tree Types
 * Represents the hierarchical structure of explorable topics
 */

export interface Subtopic {
  /** Unique identifier, e.g., "housing.rent-control" */
  id: string;
  /** Display name, e.g., "Rent Control" */
  name: string;
  /** One sentence description */
  description: string;
  /** Parties with positions on this subtopic */
  parties: string[];
  /** Exploration status */
  status: 'pending' | 'explored';
}

export interface Topic {
  /** Unique identifier, e.g., "housing" */
  id: string;
  /** Display name, e.g., "Housing" */
  name: string;
  /** Brief description */
  description: string;
  /** Child subtopics (leaf nodes) */
  subtopics: Subtopic[];
  /** Exploration status */
  status: 'pending' | 'partial' | 'explored';
}

export interface TopicTree {
  /** Unique exploration identifier */
  explorationId: string;
  /** The user's original query that started this exploration */
  originalQuery: string;
  /** Top-level topics (branch nodes) */
  topics: Topic[];
  /** When the tree was created */
  createdAt: string;
  /** When the tree was last updated */
  updatedAt: string;
}
