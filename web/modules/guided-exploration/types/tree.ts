/**
 * Exploration Tree Types
 * Position-based adaptive hierarchy for exploring party positions
 */

/** A concrete position, demand, or statement from a party */
export interface Position {
  id: string;
  partyId: string;
  content: string;
  quote: string;
  positionType: 'position' | 'measure' | 'target' | 'argument' | 'criticism';
  citation: {
    id: string;
    party: string;
    document: string;
    section?: string;
    page?: number;
    url?: string;
  } | null;
  chunkIndex: number;
}

/**
 * Recursive node in the exploration tree.
 * Can be a branch (has children) or a leaf (has positionIds).
 * Names must be screen-reader friendly.
 */
export interface ExplorationNode {
  id: string;
  /** Descriptive name — must be understandable for screen readers */
  name: string;
  description: string;
  /** Child nodes. Empty = leaf node */
  children: ExplorationNode[];
  /** Party IDs with positions in this node or its descendants */
  partyIds: string[];
  /** Position IDs assigned to this leaf. Empty for branch nodes */
  positionIds: string[];
  /**
   * Exploration status.
   * - `pending`: no content generated yet
   * - `loaded`: content pre-generated (study eager pre-gen) but user hasn't opened it
   * - `started`: user has opened the leaf
   * - `explored`: user marked the leaf as done
   */
  status: 'pending' | 'loaded' | 'started' | 'explored';
}

/** Complete exploration tree with position-based hierarchy */
export interface ExplorationTree {
  explorationId: string;
  originalQuery: string;
  /** User-selected direction focuses (from topic direction choice) */
  selectedDirections?: string[];
  /** Root node of the tree (the query topic) */
  root: ExplorationNode;
  /** Lookup: positionId -> Position */
  positions: Record<string, Position>;
  createdAt: string;
  updatedAt: string;
}
