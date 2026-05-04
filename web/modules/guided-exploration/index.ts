/**
 * Guided Exploration Module
 *
 * Multi-tree adaptive hierarchy for comparing party positions on
 * political topics. Trees render inline in the chat; leaves open in a
 * right-side sidebar via {@link useExploration}.
 */

// ============ Types ============
export type {
  // Tree types
  Position,
  ExplorationNode,
  ExplorationTree,
  // Content types
  Citation,
  PartyPosition,
  Analysis,
  SubtopicContent,
  // Conversation types
  Message,
  MessageRole,
  MessageType,
  Conversation,
  LeafSummary,
  SummaryTree,
  // Event types
  SSEEvent,
  ThinkingStage,
  ChoicePromptEvent,
  TopicTreeEvent,
  ConversationOpenedEvent,
  StreamChunkEvent,
  ErrorEvent,
  ErrorCode,
} from './types';

// ============ Store ============
export {
  useExplorationStore,
  type ExplorationStore,
} from './store';

export type {
  ExplorationStoreState,
  ExplorationAction,
  AppMode,
  ConnectionStatus,
} from './store';

// Selectors (for advanced usage)
export {
  selectIsConnected,
  selectSessionId,
  selectTrees,
  selectTreeIds,
  selectTreesArray,
  selectTree,
  selectConversation,
  selectActiveLeaf,
  selectActiveConversation,
  selectMode,
  selectIsStreaming,
  selectStreamBuffer,
  selectPendingChoice,
  selectIsThinking,
  selectError,
  selectExplorationSummaries,
  selectLeafSummary,
  selectProgress,
} from './store';

// Action creators (for advanced usage)
export {
  connectionActions,
  sessionActions,
  explorationActions,
  conversationActions,
  streamActions,
  uiActions,
  summaryActions,
} from './store';

// ============ Hooks ============
export {
  useExploration,
  type UseExplorationOptions,
} from './hooks';

export {
  useSSE,
  type UseSSEOptions,
  type UseSSEReturn,
} from './hooks';

export {
  useExplorationApi,
  type UseExplorationApiReturn,
} from './hooks';

export {
  useFirebaseSummaries,
  type UseFirebaseSummariesReturn,
} from './hooks';

// ============ Services ============
export {
  explorationApi,
  createSSEClient,
  type SSEClient,
  type SSEClientOptions,
} from './services';

// ============ Utils ============
export {
  findNode,
  getPathTo,
  isLeaf,
  getAllLeaves,
  getBranchLeaves,
  countLeaves,
  countExploredLeaves,
  getBranchProgress,
  getOverallProgress,
  hasExploredLeaves,
  isFullyExplored,
  getNextUnexploredLeaf,
  getPositionsForLeaf,
  getPositionsByParty,
  getAllParties,
} from './utils';

// ============ Components ============
export {
  // Layout
  ExplorationMain,
  // Leaf sidebar dependency
  LeafContent,
  // Shared
  ExplorationLoading,
  PartyBadge,
  ProgressIndicator,
  StatusDot,
  StatusDots,
} from './components';
