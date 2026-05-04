/**
 * Action Creators
 * Factory functions for creating typed actions
 */

import type {
  Analysis,
  ChoicePromptEvent,
  Conversation,
  ErrorCode,
  ExplorationTree,
  LeafSummary,
  Message,
  SessionMessage,
  StreamSection,
  StreamTargetType,
  ThinkingStage,
  TopicDirectionsEvent,
} from '@/modules/guided-exploration/types';
import type {
  AppMode,
  ExplorationAction,
  ExplorationStatus,
  OriginTab,
  QuickSummaryData,
} from './types';

// ============ Connection Actions ============

export const connectionActions = {
  init: (): ExplorationAction => ({ type: 'CONNECTION_INIT' }),
  connecting: (): ExplorationAction => ({ type: 'CONNECTION_CONNECTING' }),
  connected: (): ExplorationAction => ({ type: 'CONNECTION_CONNECTED' }),
  disconnected: (error?: string): ExplorationAction => ({
    type: 'CONNECTION_DISCONNECTED',
    error,
  }),
  reconnectAttempt: (): ExplorationAction => ({
    type: 'CONNECTION_RECONNECT_ATTEMPT',
  }),
  reset: (): ExplorationAction => ({ type: 'CONNECTION_RESET' }),
  sessionClaimed: (message?: string): ExplorationAction => ({
    type: 'SESSION_CLAIMED',
    message,
  }),
};

// ============ Session Actions ============

export const sessionActions = {
  created: (sessionId: string): ExplorationAction => ({
    type: 'SESSION_CREATED',
    sessionId,
  }),

  loaded: (sessionId: string): ExplorationAction => ({
    type: 'SESSION_LOADED',
    sessionId,
  }),

  cleared: (): ExplorationAction => ({ type: 'SESSION_CLEARED' }),

  messageAdded: (message: SessionMessage): ExplorationAction => ({
    type: 'SESSION_MESSAGE_ADDED',
    message,
  }),

  messageUpdated: (
    messageId: string,
    updates: Partial<SessionMessage>,
  ): ExplorationAction => ({
    type: 'SESSION_MESSAGE_UPDATED',
    messageId,
    updates,
  }),

  messagesLoaded: (messages: SessionMessage[]): ExplorationAction => ({
    type: 'SESSION_MESSAGES_LOADED',
    messages,
  }),
};

// ============ Exploration Actions ============

export const explorationActions = {
  started: (
    explorationId: string,
    tree: ExplorationTree,
    status?: ExplorationStatus,
  ): ExplorationAction => ({
    type: 'EXPLORATION_STARTED',
    explorationId,
    tree,
    status,
  }),

  statusUpdated: (
    explorationId: string,
    status: ExplorationStatus,
  ): ExplorationAction => ({
    type: 'EXPLORATION_STATUS_UPDATED',
    explorationId,
    status,
  }),

  treeReceived: (tree: ExplorationTree): ExplorationAction => ({
    type: 'EXPLORATION_TREE_RECEIVED',
    tree,
  }),

  ready: (
    explorationId: string,
    topicsCount: number,
    subtopicsCount: number,
    partiesCount: number,
  ): ExplorationAction => ({
    type: 'EXPLORATION_READY',
    explorationId,
    topicsCount,
    subtopicsCount,
    partiesCount,
  }),

  readyCleared: (): ExplorationAction => ({
    type: 'EXPLORATION_READY_CLEARED',
  }),

  ended: (explorationId: string): ExplorationAction => ({
    type: 'EXPLORATION_ENDED',
    explorationId,
  }),

  leafActivated: (
    explorationId: string,
    leafId: string,
  ): ExplorationAction => ({
    type: 'LEAF_ACTIVATED',
    explorationId,
    leafId,
  }),

  leafOpened: (
    explorationId: string,
    leafId: string,
    conversation: Conversation,
    analysisAvailable: boolean,
  ): ExplorationAction => ({
    type: 'LEAF_OPENED',
    explorationId,
    leafId,
    conversation,
    analysisAvailable,
  }),

  leafClosed: (): ExplorationAction => ({ type: 'LEAF_CLOSED' }),

  leafMarkedExplored: (
    explorationId: string,
    leafId: string,
  ): ExplorationAction => ({
    type: 'LEAF_MARKED_EXPLORED',
    explorationId,
    leafId,
  }),
};

// ============ Conversation Actions ============

export const conversationActions = {
  messageAdded: (
    explorationId: string,
    leafId: string,
    message: Message,
  ): ExplorationAction => ({
    type: 'MESSAGE_ADDED',
    explorationId,
    leafId,
    message,
  }),

  analysisReceived: (
    explorationId: string,
    leafId: string,
    analysis: Analysis,
  ): ExplorationAction => ({
    type: 'ANALYSIS_RECEIVED',
    explorationId,
    leafId,
    analysis,
  }),
};

// ============ Streaming Actions ============

export const streamActions = {
  started: (
    streamId: string,
    targetType: StreamTargetType,
    targetId: string,
    explorationId: string | null,
    leafId: string | null,
    originTab?: OriginTab,
  ): ExplorationAction => ({
    type: 'STREAM_STARTED',
    streamId,
    targetType,
    targetId,
    explorationId,
    leafId,
    originTab,
  }),

  chunkReceived: (
    streamId: string,
    chunk: string,
    section?: StreamSection,
  ): ExplorationAction => ({
    type: 'STREAM_CHUNK_RECEIVED',
    streamId,
    chunk,
    section,
  }),

  ended: (streamId: string, complete: boolean): ExplorationAction => ({
    type: 'STREAM_ENDED',
    streamId,
    complete,
  }),

  bufferCleared: (): ExplorationAction => ({ type: 'STREAM_BUFFER_CLEARED' }),
};

// ============ UI Actions ============

export const uiActions = {
  modeChanged: (mode: AppMode): ExplorationAction => ({
    type: 'MODE_CHANGED',
    mode,
  }),

  thinkingStarted: (
    stage: ThinkingStage,
    message: string,
    originTab?: OriginTab,
  ): ExplorationAction => ({
    type: 'THINKING_STARTED',
    stage,
    message,
    originTab,
  }),

  thinkingEnded: (): ExplorationAction => ({ type: 'THINKING_ENDED' }),

  choicePrompted: (
    choice: ChoicePromptEvent,
    originTab?: OriginTab,
  ): ExplorationAction => ({
    type: 'CHOICE_PROMPTED',
    choice,
    originTab,
  }),

  choiceCleared: (): ExplorationAction => ({ type: 'CHOICE_CLEARED' }),

  quickSummaryReceived: (data: QuickSummaryData): ExplorationAction => ({
    type: 'QUICK_SUMMARY_RECEIVED',
    data,
  }),

  quickSummaryCleared: (): ExplorationAction => ({
    type: 'QUICK_SUMMARY_CLEARED',
  }),

  announce: (message: string): ExplorationAction => ({
    type: 'ANNOUNCE',
    message,
  }),

  announcementCleared: (): ExplorationAction => ({
    type: 'ANNOUNCEMENT_CLEARED',
  }),

  errorOccurred: (
    code: ErrorCode,
    message: string,
    recoverable: boolean,
  ): ExplorationAction => ({
    type: 'ERROR_OCCURRED',
    code,
    message,
    recoverable,
  }),

  errorCleared: (): ExplorationAction => ({ type: 'ERROR_CLEARED' }),

  suggestedQuestionsSet: (
    questions: string[],
    originTab?: OriginTab,
  ): ExplorationAction => ({
    type: 'SUGGESTED_QUESTIONS_SET',
    questions,
    originTab,
  }),

  suggestedQuestionsCleared: (): ExplorationAction => ({
    type: 'SUGGESTED_QUESTIONS_CLEARED',
  }),

  lastActionTabSet: (tab: OriginTab): ExplorationAction => ({
    type: 'LAST_ACTION_TAB_SET',
    tab,
  }),

  topicSwitchSuggested: (
    explorationId: string,
    leafId: string,
    targetNodeId: string,
    targetNodeName: string,
    message: string,
  ): ExplorationAction => ({
    type: 'TOPIC_SWITCH_SUGGESTED',
    explorationId,
    leafId,
    targetNodeId,
    targetNodeName,
    message,
  }),

  topicSwitchCleared: (): ExplorationAction => ({
    type: 'TOPIC_SWITCH_CLEARED',
  }),

  topicDirectionsReceived: (
    directions: TopicDirectionsEvent,
  ): ExplorationAction => ({
    type: 'TOPIC_DIRECTIONS_RECEIVED',
    directions,
  }),

  topicDirectionsCleared: (): ExplorationAction => ({
    type: 'TOPIC_DIRECTIONS_CLEARED',
  }),
};

// ============ Summary Actions ============

export const summaryActions = {
  generating: (nodeId: string): ExplorationAction => ({
    type: 'SUMMARY_GENERATING',
    nodeId,
  }),

  generationDone: (nodeId: string): ExplorationAction => ({
    type: 'SUMMARY_GENERATION_DONE',
    nodeId,
  }),

  leafSummaryReceived: (
    explorationId: string,
    leafId: string,
    summary: LeafSummary,
  ): ExplorationAction => ({
    type: 'LEAF_SUMMARY_RECEIVED',
    explorationId,
    leafId,
    summary,
  }),

  topicSummaryReceived: (
    explorationId: string,
    topicId: string,
    summary: string,
  ): ExplorationAction => ({
    type: 'TOPIC_SUMMARY_RECEIVED',
    explorationId,
    topicId,
    summary,
  }),

  synced: (
    explorationId: string,
    summaries: Record<string, LeafSummary>,
  ): ExplorationAction => ({
    type: 'SUMMARIES_SYNCED',
    explorationId,
    summaries,
  }),

  cleared: (): ExplorationAction => ({ type: 'SUMMARIES_CLEARED' }),
};
