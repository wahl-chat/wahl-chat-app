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
  NavigationState,
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
  ViewType,
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

  loaded: (sessionId: string, explorationId?: string): ExplorationAction => ({
    type: 'SESSION_LOADED',
    sessionId,
    explorationId,
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

  tabSwitched: (
    tabId: 'chat' | string,
    previousPath?: string[],
  ): ExplorationAction => ({
    type: 'TAB_SWITCHED',
    tabId,
    previousPath,
  }),

  explorationTabAdded: (
    explorationId: string,
    label: string,
    colorIndex: number,
  ): ExplorationAction => ({
    type: 'EXPLORATION_TAB_ADDED',
    explorationId,
    label,
    colorIndex,
  }),

  explorationTabRemoved: (explorationId: string): ExplorationAction => ({
    type: 'EXPLORATION_TAB_REMOVED',
    explorationId,
  }),
};

// ============ Exploration Actions ============

export const explorationActions = {
  started: (
    explorationId: string,
    tree: ExplorationTree,
    navigation: NavigationState,
    status?: ExplorationStatus,
  ): ExplorationAction => ({
    type: 'EXPLORATION_STARTED',
    explorationId,
    tree,
    navigation,
    status,
  }),

  statusUpdated: (status: ExplorationStatus): ExplorationAction => ({
    type: 'EXPLORATION_STATUS_UPDATED',
    status,
  }),

  treeReceived: (
    explorationId: string,
    tree: ExplorationTree,
  ): ExplorationAction => ({
    type: 'EXPLORATION_TREE_RECEIVED',
    explorationId,
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

  navigatedToRoot: (navigation: NavigationState): ExplorationAction => ({
    type: 'NAVIGATED_TO_ROOT',
    navigation,
  }),

  navigatedToBranch: (navigation: NavigationState): ExplorationAction => ({
    type: 'NAVIGATED_TO_BRANCH',
    navigation,
  }),

  navigatedToLeaf: (
    leafId: string,
    conversation: Conversation,
    navigation: NavigationState,
    analysisAvailable: boolean,
  ): ExplorationAction => ({
    type: 'NAVIGATED_TO_LEAF',
    leafId,
    conversation,
    navigation,
    analysisAvailable,
  }),

  ended: (): ExplorationAction => ({ type: 'EXPLORATION_ENDED' }),

  leafMarkedExplored: (leafId: string): ExplorationAction => ({
    type: 'LEAF_MARKED_EXPLORED',
    leafId,
  }),
};

// ============ Conversation Actions ============

export const conversationActions = {
  opened: (
    leafId: string,
    conversation: Conversation,
    analysisAvailable: boolean,
  ): ExplorationAction => ({
    type: 'CONVERSATION_OPENED',
    leafId,
    conversation,
    analysisAvailable,
  }),

  messageAdded: (leafId: string, message: Message): ExplorationAction => ({
    type: 'MESSAGE_ADDED',
    leafId,
    message,
  }),

  analysisReceived: (
    leafId: string,
    analysis: Analysis,
  ): ExplorationAction => ({
    type: 'ANALYSIS_RECEIVED',
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
    originTab?: OriginTab,
  ): ExplorationAction => ({
    type: 'STREAM_STARTED',
    streamId,
    targetType,
    targetId,
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

  viewChanged: (view: ViewType): ExplorationAction => ({
    type: 'VIEW_CHANGED',
    view,
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
    targetNodeId: string,
    targetNodeName: string,
    message: string,
  ): ExplorationAction => ({
    type: 'TOPIC_SWITCH_SUGGESTED',
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
    leafId: string,
    summary: LeafSummary,
  ): ExplorationAction => ({
    type: 'LEAF_SUMMARY_RECEIVED',
    leafId,
    summary,
  }),

  topicSummaryReceived: (
    topicId: string,
    summary: string,
  ): ExplorationAction => ({
    type: 'TOPIC_SUMMARY_RECEIVED',
    topicId,
    summary,
  }),

  synced: (summaries: Record<string, LeafSummary>): ExplorationAction => ({
    type: 'SUMMARIES_SYNCED',
    summaries,
  }),

  cleared: (): ExplorationAction => ({ type: 'SUMMARIES_CLEARED' }),
};
