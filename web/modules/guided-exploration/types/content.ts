/**
 * Content Types
 * Represents the structured content for subtopics (leaf nodes)
 */

export interface Citation {
  /** Unique identifier */
  id: string;
  /** Party name */
  party: string;
  /** Document name, e.g., "Wahlprogramm 2025" */
  document: string;
  /** Section reference */
  section?: string;
  /** Page number */
  page?: number;
  /** URL to the source document */
  url?: string;
}

export interface PartyPosition {
  /** Party name */
  party: string;
  /** Full markdown content with inline citations [id] */
  content: string;
}

export interface Analysis {
  /** Overall assessment */
  summary: string;
  /** Background and current situation */
  context: string;
  /** Feasibility considerations */
  feasibility: string[];
  /** Other critical points */
  considerations: string[];
  /** External sources used */
  sources: string[];
}

/** A single party's stance on an aspect for comparison */
export interface PartyStance {
  /** Party ID */
  party: string;
  /** Short stance description */
  stance: string;
}

/** A comparable aspect extracted across parties */
export interface ComparisonAspect {
  /** Aspect name, e.g., "Mindestlohn" */
  name: string;
  /** Each party's stance on this aspect */
  partyStances: PartyStance[];
}

/** Structured comparison data for toggling between party and aspect views */
export interface AspectComparison {
  aspects: ComparisonAspect[];
}

export interface SubtopicContent {
  /** Subtopic identifier */
  subtopicId: string;
  /** Path in tree, e.g., ["housing", "rent-control"] */
  path: string[];
  /** 2-3 sentence overview */
  summary: string;
  /** Party positions on this subtopic */
  partyPositions: PartyPosition[];
  /** On-demand analysis (may be null) */
  analysis?: Analysis;
  /** Aspect-based comparison (generated alongside party positions) */
  aspectComparison?: AspectComparison;
  /** All citations for this content */
  citations: Citation[];
  /** Suggested follow-up questions */
  suggestedQuestions?: string[];
}
