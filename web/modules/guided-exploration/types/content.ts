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
  /** All citations for this content */
  citations: Citation[];
  /** Suggested follow-up questions */
  suggestedQuestions?: string[];
}
