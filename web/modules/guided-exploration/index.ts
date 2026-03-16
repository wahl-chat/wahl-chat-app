/**
 * Guided Exploration Module
 *
 * A tree-of-conversations exploration system for comparing party positions
 * on political topics.
 *
 * @example
 * ```tsx
 * import { useExploration, ExplorationProvider } from '@/modules/guided-exploration';
 *
 * function ExplorationPage() {
 *   const {
 *     tree,
 *     activeConversation,
 *     navigate,
 *     sendMessage,
 *   } = useExploration({ autoCreateSession: true });
 *
 *   // ... render exploration UI
 * }
 * ```
 */

// ============ Types ============
export type {
  // Tree types
  Topic,
  Subtopic,
  TopicTree,
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
  // Navigation types
  NavigationState,
  BreadcrumbItem,
  BreadcrumbLevel,
  SiblingNavigation as SiblingNavigationType,
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
  ViewType,
  ConnectionStatus,
} from './store';

// Selectors (for advanced usage)
export {
  selectIsConnected,
  selectSessionId,
  selectExplorationId,
  selectTree,
  selectNavigation,
  selectCurrentPath,
  selectBreadcrumb,
  selectActiveConversation,
  selectConversation,
  selectMode,
  selectView,
  selectIsStreaming,
  selectStreamBuffer,
  selectPendingChoice,
  selectIsThinking,
  selectError,
  selectSummaries,
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
  // Tree helpers
  findTopic,
  findSubtopic,
  getAllLeaves,
  countLeaves,
  countExploredLeaves,
  getOverallProgress,
  getTopicProgress,
  getNextUnexploredLeaf,
  getAllParties,
  // Navigation helpers
  pathFromLeafId,
  leafIdFromPath,
  getParentPath,
  isAtRoot,
  isAtTopic,
  isAtSubtopic,
  buildBreadcrumb,
  getViewFromPath,
  isValidPath,
  getPathDisplayName,
} from './utils';

// ============ Components ============
export {
  // Layout
  ExplorationMain,
  // Exploration view
  BranchContent,
  ExplorationFullView,
  ExplorationSummaryPanel,
  LeafContent,
  MobileSummarySheet,
  RootContent,
  type ExplorationView,
  // Navigation
  ExplorationBreadcrumb,
  SiblingNavigation,
  SubtopicItem,
  TopicCard,
  // Shared
  ExplorationLoading,
  PartyBadge,
  ProgressIndicator,
  StatusDot,
  StatusDots,
} from './components';
