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

export type SessionMessageType = 'user' | 'assistant' | 'exploration_start';

export interface SessionMessage {
  /** Unique message identifier */
  id: string;
  /** Type of session message */
  type: SessionMessageType;
  /** Message content */
  content: string;
  /** Citations for this message (for quick summaries) */
  citations?: Citation[];
  /** ID of the exploration if this is an exploration_start message */
  explorationId?: string;
  /** The query that triggered the exploration */
  explorationQuery?: string;
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
  /** Whether a summary has been generated for this conversation */
  hasSummary: boolean;
}

export interface LeafSummary {
  /** Leaf node identifier */
  leafId: string;
  /** 2-3 sentence overview */
  overview: string;
  /** Main takeaways */
  keyPoints: string[];
  /** Brief comparison if applicable */
  partyComparison?: string;
  /** When the summary was generated */
  generatedAt: string;
}

export interface SummaryTree {
  /** Exploration identifier */
  explorationId: string;
  /** Leaf summaries by leafId */
  summaries: Record<string, LeafSummary>;
  /** Aggregated topic summaries by topicId */
  topicSummaries: Record<string, string>;
}
