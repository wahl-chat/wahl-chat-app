/**
 * SSE Event Types
 * All server-sent event payloads
 */

import type { Analysis, Citation } from './content';
import type { Conversation } from './conversation';
import type { NavigationState, SiblingNavigation } from './navigation';
import type { ExplorationNode, ExplorationTree } from './tree';

// ============ Connection Events ============

export interface ConnectedEvent {
  type: 'connected';
}

export interface SessionClaimedEvent {
  type: 'session_claimed';
  /** Message explaining the session was claimed */
  message?: string;
}

// ============ Thinking Events ============

export type ThinkingStage =
  | 'classifying'
  | 'planning'
  | 'retrieving'
  | 'generating';

export interface ThinkingEvent {
  type: 'thinking';
  stage: ThinkingStage;
  message: string;
}

// ============ Choice Events ============

export interface ChoiceOption {
  id: 'summary' | 'explore';
  label: string;
  description: string;
}

export interface ChoicePromptEvent {
  type: 'choice_prompt';
  queryId: string;
  originalQuery: string;
  options: [ChoiceOption, ChoiceOption];
}

// ============ Tree Events ============

export interface TopicTreeEvent {
  type: 'topic_tree';
  explorationId: string;
  tree: ExplorationTree;
  navigation: NavigationState;
  isUpdate: boolean;
}

export interface TopicOverviewEvent {
  type: 'topic_overview';
  topicId: string;
  name: string;
  description: string;
  children: ExplorationNode[];
  navigation: NavigationState;
}

// ============ Conversation Events ============

export interface ConversationOpenedEvent {
  type: 'conversation_opened';
  leafId: string;
  conversation: Conversation;
  navigation: NavigationState;
  analysisAvailable: boolean;
  siblingNavigation: SiblingNavigation;
  /** Suggested follow-up questions */
  suggestedQuestions?: string[];
}

export interface ConversationMessageEvent {
  type: 'conversation_message';
  leafId: string;
  message: Conversation['messages'][number];
  navigation?: NavigationState;
  /** Citations for this message */
  citations?: Citation[];
  /** Suggested follow-up questions */
  suggestedQuestions?: string[];
}

// ============ Summary Events ============

export type SummaryStatus = 'started' | 'completed' | 'failed';

export interface SummaryGeneratingEvent {
  type: 'summary_generating';
  leafId: string;
  status: SummaryStatus;
  error?: string;
}

// ============ Analysis Events ============

export interface AnalysisResultEvent {
  type: 'analysis_result';
  leafId: string;
  analysis: Analysis;
}

// ============ Quick Summary Events ============

export interface QuickSummaryEvent {
  type: 'quick_summary';
  queryId: string;
  originalQuery: string;
  text: string;
  citations: Citation[];
  canExploreDeeper: boolean;
  /** Suggested follow-up questions */
  suggestedQuestions?: string[];
}

// ============ Chat Message Events ============

export interface ChatMessageEvent {
  type: 'chat_message';
  messageId: string;
  content: string;
  citations: Citation[];
  canExploreDeeper: boolean;
  queryId: string;
  /** Suggested follow-up questions */
  suggestedQuestions?: string[];
}

// ============ Streaming Events ============

export type StreamTargetType =
  | 'initial_content'
  | 'followup'
  | 'analysis'
  | 'quick_summary';

export type StreamSection =
  | 'summary'
  | 'party_positions'
  | 'measures'
  | 'analysis';

export interface StreamChunkEvent {
  type: 'stream_chunk';
  streamId: string;
  targetType: StreamTargetType;
  targetId: string;
  section?: StreamSection;
  chunk: string;
  chunkIndex: number;
}

export interface StreamEndEvent {
  type: 'stream_end';
  streamId: string;
  targetType: string;
  targetId: string;
  complete: boolean;
}

// ============ Exploration Ready Events ============

export interface ExplorationReadyEvent {
  type: 'exploration_ready';
  explorationId: string;
  topicsCount: number;
  subtopicsCount: number;
  partiesCount: number;
}

// ============ Exploration Complete Events ============

export interface ExplorationCompleteEvent {
  type: 'exploration_complete';
  explorationId: string;
  closingSummary: string;
  stats: {
    topicsExplored: number;
    topicsTotal: number;
    questionsAsked: number;
  };
  nextActions: {
    readFullSummary: boolean;
    downloadPdf: boolean;
    continueExploring: boolean;
  };
  unexploredTopics: Array<{
    id: string;
    name: string;
  }>;
}

// ============ Export Events ============

export interface ExportReadyEvent {
  type: 'export_ready';
  explorationId: string;
  exportId: string;
  downloadUrl: string;
  expiresAt: string;
  filename: string;
}

// ============ Topic Switch Events ============

export interface TopicSwitchSuggestedEvent {
  type: 'topic_switch_suggested';
  leafId: string;
  targetNodeId: string;
  targetNodeName: string;
  message: string;
}

// ============ Topic Directions Events ============

export interface TopicDirectionItem {
  id: string;
  name: string;
  description: string;
  partyStancesPreview: string;
  suggestedQuestion: string;
}

export interface TopicDirectionsEvent {
  type: 'topic_directions';
  queryId: string;
  originalQuery: string;
  directions: TopicDirectionItem[];
}

// ============ Error Events ============

export type ErrorCode =
  | 'SESSION_EXPIRED'
  | 'EXPLORATION_NOT_FOUND'
  | 'NAVIGATION_INVALID'
  | 'RETRIEVAL_FAILED'
  | 'LLM_ERROR'
  | 'RATE_LIMITED'
  | 'EXPORT_FAILED';

export interface ErrorEvent {
  type: 'error';
  code: ErrorCode;
  message: string;
  recoverable: boolean;
  suggestedAction?: string;
}

// ============ Union Type ============

export type SSEEvent =
  | ConnectedEvent
  | SessionClaimedEvent
  | ThinkingEvent
  | ChoicePromptEvent
  | TopicTreeEvent
  | TopicOverviewEvent
  | ConversationOpenedEvent
  | ConversationMessageEvent
  | SummaryGeneratingEvent
  | AnalysisResultEvent
  | QuickSummaryEvent
  | ChatMessageEvent
  | StreamChunkEvent
  | StreamEndEvent
  | ExplorationReadyEvent
  | ExplorationCompleteEvent
  | ExportReadyEvent
  | ErrorEvent
  | TopicSwitchSuggestedEvent
  | TopicDirectionsEvent;
