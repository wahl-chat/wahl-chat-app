/**
 * Guided Exploration Module
 *
 * A claim-based adaptive hierarchy for comparing party positions
 * on political topics. Uses recursive ExplorationNode tree structure.
 *
 * @example
 * ```tsx
 * import { useExploration } from '@/modules/guided-exploration';
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
  Claim,
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
  getClaimsForLeaf,
  getClaimsByParty,
  getAllParties,
  // Navigation helpers
  getParentPath,
  isAtRoot,
  buildBreadcrumb,
  getSiblingNavigation,
  getViewFromNodeId,
  isValidNodeId,
  getNodeDisplayName,
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
