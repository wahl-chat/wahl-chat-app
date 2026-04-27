/**
 * Exploration Store
 * Main Zustand store combining all slices with reducer pattern
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';

import type { BreadcrumbItem } from '@/modules/guided-exploration/types';
import {
  countExploredLeaves,
  countLeaves,
} from '@/modules/guided-exploration/utils/tree-helpers';
import {
  connectionReducer,
  explorationReducer,
  initialConnectionState,
  initialExplorationState,
  initialSessionState,
  initialSummariesState,
  initialUIState,
  sessionReducer,
  summariesReducer,
  uiReducer,
} from './slices';
import type { ExplorationAction, ExplorationStoreState } from './types';

import type { SessionMessage } from '@/modules/guided-exploration/types';

// ============ Stable References (for selector stability) ============
const EMPTY_PATH: string[] = [];
const EMPTY_BREADCRUMB: BreadcrumbItem[] = [];
const EMPTY_MESSAGES: SessionMessage[] = [];

// ============ Initial State ============

const initialState: ExplorationStoreState = {
  connection: initialConnectionState,
  session: initialSessionState,
  exploration: initialExplorationState,
  ui: initialUIState,
  summaries: initialSummariesState,
};

// ============ Root Reducer ============

function rootReducer(
  state: ExplorationStoreState,
  action: ExplorationAction,
): ExplorationStoreState {
  return {
    connection: connectionReducer(state.connection, action),
    session: sessionReducer(state.session, action),
    exploration: explorationReducer(state.exploration, action),
    ui: uiReducer(state.ui, action),
    summaries: summariesReducer(state.summaries, action),
  };
}

// ============ Store Interface ============

export interface ExplorationStore extends ExplorationStoreState {
  /** Dispatch an action to update state */
  dispatch: (action: ExplorationAction) => void;

  /** Reset entire store to initial state */
  reset: () => void;
}

// ============ Store Creation ============

export const useExplorationStore = create<ExplorationStore>()(
  devtools(
    subscribeWithSelector((set) => ({
      ...initialState,

      dispatch: (action) => {
        set(
          (state) => rootReducer(state, action),
          false,
          // Action type for Redux DevTools
          action.type,
        );
      },

      reset: () => {
        set(initialState, false, 'RESET');
      },
    })),
    {
      name: 'guided-exploration',
      enabled: process.env.NODE_ENV === 'development',
    },
  ),
);

// ============ Selectors ============

/** Check if SSE is connected */
export const selectIsConnected = (state: ExplorationStore) =>
  state.connection.status === 'connected';

/** Get current session ID */
export const selectSessionId = (state: ExplorationStore) =>
  state.session.sessionId;

/** Get current exploration ID */
export const selectExplorationId = (state: ExplorationStore) =>
  state.session.explorationId;

/** Get the topic tree */
export const selectTree = (state: ExplorationStore) => state.exploration.tree;

/** Get current navigation state */
export const selectNavigation = (state: ExplorationStore) =>
  state.exploration.navigation;

/** Get current path in tree */
export const selectCurrentPath = (state: ExplorationStore) =>
  state.exploration.navigation?.currentPath ?? EMPTY_PATH;

/** Get breadcrumb items */
export const selectBreadcrumb = (state: ExplorationStore) =>
  state.exploration.navigation?.breadcrumb ?? EMPTY_BREADCRUMB;

/** Get the active leaf conversation */
export const selectActiveConversation = (state: ExplorationStore) => {
  const { activeLeafId, conversations } = state.exploration;
  return activeLeafId ? (conversations[activeLeafId] ?? null) : null;
};

/** Get a specific conversation by leaf ID */
export const selectConversation =
  (leafId: string) => (state: ExplorationStore) =>
    state.exploration.conversations[leafId] ?? null;

/** Check if analysis is available for current leaf */
export const selectAnalysisAvailable = (state: ExplorationStore) =>
  state.exploration.analysisAvailable;

/** Get the lifecycle status of the current exploration */
export const selectExplorationStatus = (state: ExplorationStore) =>
  state.exploration.status;

/** Get current app mode */
export const selectMode = (state: ExplorationStore) => state.ui.mode;

/** Get current view type */
export const selectView = (state: ExplorationStore) => state.ui.view;

/** Check if currently streaming */
export const selectIsStreaming = (state: ExplorationStore) =>
  state.ui.isStreaming;

/** Get stream buffer content */
export const selectStreamBuffer = (state: ExplorationStore) =>
  state.ui.streamBuffer;

/** Get streaming target info */
export const selectStreamingTarget = (state: ExplorationStore) =>
  state.ui.streamingTarget;

/** Tab the active stream belongs to (chat / leaf / null=unknown). */
export const selectStreamingOriginTab = (state: ExplorationStore) =>
  state.ui.streamingOriginTab;

/** Get pending choice prompt */
export const selectPendingChoice = (state: ExplorationStore) =>
  state.ui.pendingChoice;

/** Tab the pending choice belongs to. */
export const selectPendingChoiceOriginTab = (state: ExplorationStore) =>
  state.ui.pendingChoiceOriginTab;

/** Get quick summary (if in chat mode) */
export const selectQuickSummary = (state: ExplorationStore) =>
  state.ui.quickSummary;

/** Get thinking stage */
export const selectThinkingStage = (state: ExplorationStore) =>
  state.ui.thinkingStage;

/** Get thinking message */
export const selectThinkingMessage = (state: ExplorationStore) =>
  state.ui.thinkingMessage;

/** Check if thinking */
export const selectIsThinking = (state: ExplorationStore) =>
  state.ui.thinkingStage !== null;

/** Tab the active thinking indicator belongs to. */
export const selectThinkingOriginTab = (state: ExplorationStore) =>
  state.ui.thinkingOriginTab;

/** Get current announcement for screen readers */
export const selectAnnouncement = (state: ExplorationStore) =>
  state.ui.announcement;

/**
 * Monotonic counter that increments on every announcement. Pair with
 * `selectAnnouncement` and key on this value so identical back-to-back
 * messages still trigger a re-announce.
 */
export const selectAnnouncementId = (state: ExplorationStore) =>
  state.ui.announcementId;

/** Get current error */
export const selectError = (state: ExplorationStore) => state.ui.error;

/** Get all leaf summaries */
export const selectSummaries = (state: ExplorationStore) =>
  state.summaries.summaries;

/** Get summary for a specific leaf */
export const selectLeafSummary =
  (leafId: string) => (state: ExplorationStore) =>
    state.summaries.summaries[leafId] ?? null;

/** Get topic summaries */
export const selectTopicSummaries = (state: ExplorationStore) =>
  state.summaries.topicSummaries;

/** Check if a node is currently generating summary */
export const selectIsGeneratingSummary =
  (nodeId: string) => (state: ExplorationStore) =>
    state.summaries.generatingIds.includes(nodeId);

/** Count explored leaves (leaves where status === 'explored') */
export const selectExploredCount = (state: ExplorationStore) => {
  const tree = state.exploration.tree;
  if (!tree) return 0;
  return countExploredLeaves(tree);
};

/** Count total leaves in tree */
export const selectTotalLeavesCount = (state: ExplorationStore) => {
  const tree = state.exploration.tree;
  if (!tree) return 0;
  return countLeaves(tree);
};

/** Get exploration progress as fraction */
export const selectProgress = (state: ExplorationStore) => {
  const explored = selectExploredCount(state);
  const total = selectTotalLeavesCount(state);
  return total > 0 ? explored / total : 0;
};

/** Get session messages (chat history) */
export const selectSessionMessages = (state: ExplorationStore) =>
  state.session.messages.length > 0 ? state.session.messages : EMPTY_MESSAGES;

/** Check if exploration tree preview is pending (waiting for exploration_ready) */
export const selectExplorationPending = (state: ExplorationStore) =>
  state.ui.explorationPending;

/** Get exploration ready data for auto-navigation */
export const selectExplorationReadyData = (state: ExplorationStore) =>
  state.ui.explorationReadyData;

/** Get suggested follow-up questions */
export const selectSuggestedQuestions = (state: ExplorationStore) =>
  state.ui.suggestedQuestions;

/** Tab the active suggested-questions list belongs to. */
export const selectSuggestedQuestionsOriginTab = (state: ExplorationStore) =>
  state.ui.suggestedQuestionsOriginTab;

/** Get topic switch suggestion */
export const selectTopicSwitchSuggestion = (state: ExplorationStore) =>
  state.ui.topicSwitchSuggestion;

/** Get pending topic directions */
export const selectPendingDirections = (state: ExplorationStore) =>
  state.ui.pendingDirections;

/** Get active tab ID */
export const selectActiveTabId = (state: ExplorationStore) =>
  state.session.activeTabId;

/** Get all exploration tabs */
export const selectExplorationTabs = (state: ExplorationStore) =>
  state.session.explorationTabs;
