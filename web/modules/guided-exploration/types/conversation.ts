/**
 * Conversation Types
 * Represents messages and conversations within leaf nodes
 */

import type { Citation, SubtopicContent } from './content';

export type MessageRole = 'system' | 'user' | 'assistant';
export type MessageType =
  | 'initial_content'
  | 'followup'
  | 'analysis'
  | 'system_message';

// ============ Session Messages ============

export type SessionMessageType =
  | 'user'
  | 'assistant'
  | 'exploration_start'
  | 'topic_directions';

export interface PartyStanceSummary {
  partyId: string;
  summary: string;
}

export interface ExplorationOverview {
  introParagraph: string;
  partySummaries: PartyStanceSummary[];
}

export interface SessionMessage {
  /** Unique message identifier */
  id: string;
  /** Type of session message */
  type: SessionMessageType;
  /** Message content (null for structured messages like exploration_start) */
  content: string | null;
  /** Citations for this message (for quick summaries) */
  citations?: Citation[];
  /** ID of the exploration if this is an exploration_start message */
  explorationId?: string;
  /** The query that triggered the exploration */
  explorationQuery?: string;
  /** Topic direction choices (for topic_directions type) */
  directions?: Array<{
    id: string;
    name: string;
    hook: string;
    suggestedQuestion: string;
  }>;
  /** Query ID for direction choice tracking */
  directionsQueryId?: string;
  /** Names of directions the user selected (set after submission) */
  selectedDirections?: string[];
  /** When the message was created */
  timestamp: string;
}

export interface Message {
  /** Unique message identifier */
  id: string;
  /** Who sent the message */
  role: MessageRole;
  /** Type of message */
  type: MessageType;
  /** Message content - string for followups, structured for initial content */
  content: string | SubtopicContent;
  /** Citations for followup messages */
  citations?: Citation[];
  /** When the message was created */
  timestamp: string;
}

export interface Conversation {
  /** Leaf node identifier this conversation belongs to */
  leafId: string;
  /** All messages in this conversation */
  messages: Message[];
}
