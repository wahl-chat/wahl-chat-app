/**
 * Exploration Store
 * Main Zustand store combining all slices with reducer pattern
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';

import { findNode } from '@/modules/guided-exploration/utils/tree-helpers';
import {
  connectionReducer,
  explorationReducer,
  initialConnectionState,
  initialExplorationState,
  initialSessionState,
  initialUIState,
  sessionReducer,
  uiReducer,
} from './slices';
import type { ExplorationAction, ExplorationStoreState } from './types';

import type {
  ExplorationNode,
  ExplorationTree,
  SessionMessage,
} from '@/modules/guided-exploration/types';

// ============ Stable References (for selector stability) ============
const EMPTY_MESSAGES: SessionMessage[] = [];
const EMPTY_TREES: ExplorationTree[] = [];

// ============ Initial State ============

const initialState: ExplorationStoreState = {
  connection: initialConnectionState,
  session: initialSessionState,
  exploration: initialExplorationState,
  ui: initialUIState,
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

// ----- Multi-tree -----

/** A specific tree by explorationId. */
export const selectTree =
  (explorationId: string | null | undefined) => (state: ExplorationStore) =>
    explorationId ? (state.exploration.trees[explorationId] ?? null) : null;

/** Structured overview that ships alongside the tree. */
export const selectOverview =
  (explorationId: string | null | undefined) => (state: ExplorationStore) =>
    explorationId ? (state.exploration.overviews[explorationId] ?? null) : null;

/** Currently open leaf sidebar pointer. */
export const selectActiveLeaf = (state: ExplorationStore) =>
  state.exploration.activeLeaf;

/** Tree of the currently open leaf. */
export const selectActiveLeafTree = (state: ExplorationStore) => {
  const active = state.exploration.activeLeaf;
  return active
    ? (state.exploration.trees[active.explorationId] ?? null)
    : null;
};

/** Node of the currently open leaf. */
export const selectActiveLeafNode = (
  state: ExplorationStore,
): ExplorationNode | null => {
  const active = state.exploration.activeLeaf;
  if (!active) return null;
  const tree = state.exploration.trees[active.explorationId];
  if (!tree) return null;
  return findNode(tree, active.leafId) ?? null;
};

/** Conversation of the currently open leaf. */
export const selectActiveConversation = (state: ExplorationStore) => {
  const active = state.exploration.activeLeaf;
  if (!active) return null;
  return (
    state.exploration.conversations[active.explorationId]?.[active.leafId] ??
    null
  );
};

/**
 * All trees as an array. Wrap with `useShallow` at the call site — this
 * returns a fresh array on every call and would loop
 * `useSyncExternalStore` otherwise.
 */
export const selectTreesArray = (state: ExplorationStore) => {
  const trees = state.exploration.trees;
  const keys = Object.keys(trees);
  if (keys.length === 0) return EMPTY_TREES;
  return keys.map((id) => trees[id]);
};

// ----- UI -----

/** Get current app mode */
export const selectMode = (state: ExplorationStore) => state.ui.mode;

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

/** Monotonic counter that increments on every announcement. */
export const selectAnnouncementId = (state: ExplorationStore) =>
  state.ui.announcementId;

/** Get current error */
export const selectError = (state: ExplorationStore) => state.ui.error;

// ----- Session -----

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

/** Get pending topic directions */
export const selectPendingDirections = (state: ExplorationStore) =>
  state.ui.pendingDirections;
