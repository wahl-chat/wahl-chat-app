/**
 * Exploration Tree Types
 * Claim-based adaptive hierarchy for exploring party positions
 */

/** A concrete position, demand, or statement from a party */
export interface Claim {
  id: string;
  partyId: string;
  content: string;
  quote: string;
  claimType: 'position' | 'measure' | 'target' | 'argument' | 'criticism';
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
 * Can be a branch (has children) or a leaf (has claimIds).
 * Names must be screen-reader friendly.
 */
export interface ExplorationNode {
  id: string;
  /** Descriptive name — must be understandable for screen readers */
  name: string;
  description: string;
  /** Child nodes. Empty = leaf node */
  children: ExplorationNode[];
  /** Party IDs with claims in this node or its descendants */
  partyIds: string[];
  /** Claim IDs assigned to this leaf. Empty for branch nodes */
  claimIds: string[];
  status: 'pending' | 'explored';
}

/** Complete exploration tree with claim-based hierarchy */
export interface ExplorationTree {
  explorationId: string;
  originalQuery: string;
  /** Root node of the tree (the query topic) */
  root: ExplorationNode;
  /** Lookup: claimId -> Claim */
  claims: Record<string, Claim>;
  createdAt: string;
  updatedAt: string;
}
