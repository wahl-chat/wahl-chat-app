/**
 * Store Types
 * State shapes and action definitions for the exploration store
 */

import type {
  Analysis,
  ChoicePromptEvent,
  Conversation,
  ErrorCode,
  LeafSummary,
  Message,
  NavigationState,
  SessionMessage,
  StreamSection,
  StreamTargetType,
  ThinkingStage,
  TopicTree,
} from '@/modules/guided-exploration/types';

// ============ State Slices ============

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'disconnected';

export interface ConnectionSliceState {
  status: ConnectionStatus;
  error: string | null;
  reconnectAttempts: number;
  /** Whether this session was claimed by another tab */
  sessionClaimed: boolean;
}

export interface SessionSliceState {
  sessionId: string | null;
  explorationId: string | null;
  /** Chat messages at session level */
  messages: SessionMessage[];
}

export interface ExplorationSliceState {
  tree: TopicTree | null;
  navigation: NavigationState | null;
  conversations: Record<string, Conversation>;
  activeLeafId: string | null;
  analysisAvailable: boolean;
}

export type AppMode = 'idle' | 'chat' | 'choosing' | 'exploring';
export type ViewType = 'root' | 'branch' | 'leaf';

export interface ExplorationReadyData {
  explorationId: string;
  topicsCount: number;
  subtopicsCount: number;
  partiesCount: number;
}

/** Quick summary data stored in state */
export interface QuickSummaryData {
  queryId: string;
  originalQuery: string;
  text: string;
  citations: Array<{ id: string; party: string; document: string }>;
  canExploreDeeper: boolean;
  suggestedQuestions?: string[];
}

export interface UISliceState {
  mode: AppMode;
  view: ViewType;
  isStreaming: boolean;
  streamingTarget: {
    streamId: string;
    type: StreamTargetType;
    id: string;
    section?: StreamSection;
  } | null;
  streamBuffer: string;
  pendingChoice: ChoicePromptEvent | null;
  quickSummary: QuickSummaryData | null;
  thinkingStage: ThinkingStage | null;
  thinkingMessage: string | null;
  announcement: string | null;
  error: {
    code: ErrorCode;
    message: string;
    recoverable: boolean;
  } | null;
  /** Tree preview being shown while exploration loads */
  explorationPending: boolean;
  /** Exploration ready data for auto-navigation */
  explorationReadyData: ExplorationReadyData | null;
  /** Suggested follow-up questions to show above the input */
  suggestedQuestions: string[];
}

export interface SummariesSliceState {
  summaries: Record<string, LeafSummary>;
  topicSummaries: Record<string, string>;
  generatingIds: string[];
}

// ============ Combined State ============

export interface ExplorationStoreState {
  connection: ConnectionSliceState;
  session: SessionSliceState;
  exploration: ExplorationSliceState;
  ui: UISliceState;
  summaries: SummariesSliceState;
}

// ============ Actions (Discriminated Union) ============

export type ExplorationAction =
  // Connection Actions
  | { type: 'CONNECTION_INIT' }
  | { type: 'CONNECTION_CONNECTING' }
  | { type: 'CONNECTION_CONNECTED' }
  | { type: 'CONNECTION_DISCONNECTED'; error?: string }
  | { type: 'CONNECTION_RECONNECT_ATTEMPT' }
  | { type: 'CONNECTION_RESET' }
  | { type: 'SESSION_CLAIMED'; message?: string }

  // Session Actions
  | { type: 'SESSION_CREATED'; sessionId: string }
  | {
      type: 'SESSION_LOADED';
      sessionId: string;
      explorationId?: string;
    }
  | { type: 'SESSION_CLEARED' }
  | { type: 'SESSION_MESSAGE_ADDED'; message: SessionMessage }
  | { type: 'SESSION_MESSAGES_LOADED'; messages: SessionMessage[] }

  // Exploration Actions
  | {
      type: 'EXPLORATION_STARTED';
      explorationId: string;
      tree: TopicTree;
      navigation: NavigationState;
    }
  | {
      type: 'EXPLORATION_TREE_RECEIVED';
      explorationId: string;
      tree: TopicTree;
    }
  | {
      type: 'EXPLORATION_READY';
      explorationId: string;
      topicsCount: number;
      subtopicsCount: number;
      partiesCount: number;
    }
  | { type: 'EXPLORATION_READY_CLEARED' }
  | { type: 'TREE_UPDATED'; tree: TopicTree }
  | {
      type: 'NAVIGATED_TO_ROOT';
      navigation: NavigationState;
    }
  | {
      type: 'NAVIGATED_TO_BRANCH';
      navigation: NavigationState;
    }
  | {
      type: 'NAVIGATED_TO_LEAF';
      leafId: string;
      conversation: Conversation;
      navigation: NavigationState;
      analysisAvailable: boolean;
    }
  | { type: 'EXPLORATION_ENDED' }

  // Conversation Actions
  | {
      type: 'CONVERSATION_OPENED';
      leafId: string;
      conversation: Conversation;
      analysisAvailable: boolean;
    }
  | { type: 'MESSAGE_ADDED'; leafId: string; message: Message }
  | { type: 'ANALYSIS_RECEIVED'; leafId: string; analysis: Analysis }

  // Streaming Actions
  | {
      type: 'STREAM_STARTED';
      streamId: string;
      targetType: StreamTargetType;
      targetId: string;
    }
  | {
      type: 'STREAM_CHUNK_RECEIVED';
      streamId: string;
      chunk: string;
      section?: StreamSection;
    }
  | { type: 'STREAM_ENDED'; streamId: string; complete: boolean }
  | { type: 'STREAM_BUFFER_CLEARED' }

  // UI Actions
  | { type: 'MODE_CHANGED'; mode: AppMode }
  | { type: 'VIEW_CHANGED'; view: ViewType }
  | {
      type: 'THINKING_STARTED';
      stage: ThinkingStage;
      message: string;
    }
  | { type: 'THINKING_ENDED' }
  | { type: 'CHOICE_PROMPTED'; choice: ChoicePromptEvent }
  | { type: 'CHOICE_CLEARED' }
  | { type: 'QUICK_SUMMARY_RECEIVED'; data: QuickSummaryData }
  | { type: 'QUICK_SUMMARY_CLEARED' }
  | { type: 'ANNOUNCE'; message: string }
  | { type: 'ANNOUNCEMENT_CLEARED' }
  | {
      type: 'ERROR_OCCURRED';
      code: ErrorCode;
      message: string;
      recoverable: boolean;
    }
  | { type: 'ERROR_CLEARED' }
  | { type: 'SUGGESTED_QUESTIONS_SET'; questions: string[] }
  | { type: 'SUGGESTED_QUESTIONS_CLEARED' }

  // Summary Actions
  | { type: 'SUMMARY_GENERATING'; nodeId: string }
  | { type: 'SUMMARY_GENERATION_DONE'; nodeId: string }
  | { type: 'LEAF_SUMMARY_RECEIVED'; leafId: string; summary: LeafSummary }
  | { type: 'TOPIC_SUMMARY_RECEIVED'; topicId: string; summary: string }
  | { type: 'SUMMARIES_SYNCED'; summaries: Record<string, LeafSummary> }
  | { type: 'SUMMARIES_CLEARED' }

  // Mark Explored Action
  | { type: 'LEAF_MARKED_EXPLORED'; leafId: string };
