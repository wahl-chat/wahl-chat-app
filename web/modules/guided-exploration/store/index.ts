/**
 * Store Exports
 * Public API for the exploration store
 */

// Main store hook
export {
  useExplorationStore,
  type ExplorationStore,
} from './exploration-store';

// Selectors
export {
  selectIsConnected,
  selectSessionId,
  selectTreesArray,
  selectTree,
  selectActiveLeaf,
  selectActiveLeafTree,
  selectActiveLeafNode,
  selectActiveConversation,
  selectMode,
  selectIsStreaming,
  selectStreamBuffer,
  selectStreamingTarget,
  selectStreamingOriginTab,
  selectPendingChoice,
  selectPendingChoiceOriginTab,
  selectQuickSummary,
  selectThinkingMessage,
  selectIsThinking,
  selectThinkingOriginTab,
  selectAnnouncement,
  selectAnnouncementId,
  selectError,
  selectSessionMessages,
  selectExplorationPending,
  selectExplorationReadyData,
  selectSuggestedQuestions,
  selectSuggestedQuestionsOriginTab,
  selectPendingDirections,
} from './exploration-store';

// Action creators
export {
  connectionActions,
  sessionActions,
  explorationActions,
  conversationActions,
  streamActions,
  uiActions,
} from './actions';

// Types
export type {
  ExplorationStoreState,
  ExplorationAction,
  ConnectionSliceState,
  SessionSliceState,
  ExplorationSliceState,
  ExplorationStatus,
  ActiveLeafPointer,
  StreamingTarget,
  TopicSwitchSuggestion,
  UISliceState,
  ConnectionStatus,
  AppMode,
  ExplorationReadyData,
  OriginTab,
  QuickSummaryData,
} from './types';
