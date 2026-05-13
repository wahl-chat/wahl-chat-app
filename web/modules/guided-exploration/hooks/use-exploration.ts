/**
 * useExploration Hook
 * Multi-tree public surface combining store state, SSE, and API.
 *
 * Origin gating: chat* and leaf* derived state already filter by the
 * `streamingOriginTab` / `thinkingOriginTab` / `suggestedQuestionsOriginTab`
 * fields stamped on action dispatch. Consumers no longer have to reproduce
 * `isForChatTab` / `isForLeafTab` at the call site.
 */

'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { useShallow } from 'zustand/react/shallow';

import { explorationApi as explorationApiService } from '@/modules/guided-exploration/services/exploration-api';
import {
  explorationActions,
  selectActiveConversation,
  selectActiveLeaf,
  selectActiveLeafNode,
  selectActiveLeafTree,
  selectError,
  selectExplorationPending,
  selectExplorationReadyData,
  selectIsConnected,
  selectIsStreaming,
  selectIsThinking,
  selectMode,
  selectPendingChoice,
  selectPendingChoiceOriginTab,
  selectPendingDirections,
  selectQuickSummary,
  selectSessionId,
  selectSessionMessages,
  selectStreamBuffer,
  selectStreamingOriginTab,
  selectStreamingTarget,
  selectSuggestedQuestions,
  selectSuggestedQuestionsOriginTab,
  selectThinkingMessage,
  selectThinkingOriginTab,
  selectTreesArray,
  sessionActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import type {
  Conversation,
  ExplorationTree,
  SessionMessage,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import {
  countExploredLeaves,
  countLeaves,
  getPathTo,
} from '@/modules/guided-exploration/utils/tree-helpers';

import { useExplorationApi } from './use-exploration-api';
import { useSSE } from './use-sse';

export interface UseExplorationOptions {
  /** Session ID to restore (optional) */
  initialSessionId?: string;
  /** Auto-create session if none exists */
  autoCreateSession?: boolean;
}

export interface ExplorationProgress {
  explored: number;
  total: number;
  percentage: number;
}

/**
 * Main hook for guided exploration functionality.
 * Combines state, SSE connection, and API methods. The surface is
 * multi-tree: callers pass `explorationId` to address a specific tree.
 */
export function useExploration(options: UseExplorationOptions = {}) {
  const { initialSessionId, autoCreateSession = false } = options;

  const dispatch = useExplorationStore((s) => s.dispatch);

  // ----- Session-level state -----
  const sessionId = useExplorationStore(selectSessionId);
  const isConnected = useExplorationStore(selectIsConnected);
  const mode = useExplorationStore(selectMode);
  const error = useExplorationStore(selectError);
  const sessionMessages = useExplorationStore(selectSessionMessages);

  // ----- Multi-tree state -----
  // `selectTreesArray` returns a new array reference on every call;
  // wrap with `useShallow` so identity-based snapshot comparison stops
  // looping when nothing actually changed.
  const trees = useExplorationStore(useShallow(selectTreesArray));

  // ----- Active leaf -----
  const activeLeaf = useExplorationStore(selectActiveLeaf);
  const activeLeafTree = useExplorationStore(selectActiveLeafTree);
  const activeLeafNode = useExplorationStore(selectActiveLeafNode);
  const activeConversation = useExplorationStore(selectActiveConversation);

  // ----- UI / streaming / thinking -----
  const isStreaming = useExplorationStore(selectIsStreaming);
  const streamBuffer = useExplorationStore(selectStreamBuffer);
  const streamingTarget = useExplorationStore(selectStreamingTarget);
  const streamingOriginTab = useExplorationStore(selectStreamingOriginTab);
  const thinkingMessage = useExplorationStore(selectThinkingMessage);
  const isThinking = useExplorationStore(selectIsThinking);
  const thinkingOriginTab = useExplorationStore(selectThinkingOriginTab);
  const pendingChoice = useExplorationStore(selectPendingChoice);
  const pendingChoiceOriginTab = useExplorationStore(
    selectPendingChoiceOriginTab,
  );
  const quickSummary = useExplorationStore(selectQuickSummary);
  const suggestedQuestions = useExplorationStore(selectSuggestedQuestions);
  const suggestedQuestionsOriginTab = useExplorationStore(
    selectSuggestedQuestionsOriginTab,
  );
  const topicSwitchSuggestion = useExplorationStore(
    (s) => s.ui.topicSwitchSuggestion,
  );
  const closurePrompt = useExplorationStore((s) => s.ui.closurePrompt);
  const pendingDirections = useExplorationStore(selectPendingDirections);

  const explorationPending = useExplorationStore(selectExplorationPending);
  const explorationReadyData = useExplorationStore(selectExplorationReadyData);

  // ----- SSE + API -----
  const { connect, disconnect } = useSSE({ autoConnect: true });
  const api = useExplorationApi();
  const { resumeSession, createSession } = api;

  // ----- Init session -----
  useEffect(() => {
    const initSession = async () => {
      if (initialSessionId) {
        try {
          await resumeSession(initialSessionId);
        } catch (e) {
          console.error('Failed to restore session:', e);
          if (autoCreateSession) {
            await createSession();
          }
        }
      } else if (
        autoCreateSession &&
        // Read sessionId at call time rather than closing over the
        // render-time value so a concurrent SESSION_LOADED dispatch
        // is observed.
        !useExplorationStore.getState().session.sessionId
      ) {
        await createSession();
      }
    };

    initSession();
  }, [initialSessionId, autoCreateSession, resumeSession, createSession]);

  // ----- Helpers -----
  const clearError = useCallback(() => {
    dispatch(uiActions.errorCleared());
  }, [dispatch]);

  const clearExplorationReady = useCallback(() => {
    dispatch(explorationActions.readyCleared());
  }, [dispatch]);

  const getTree = useCallback(
    (explorationId: string | null | undefined): ExplorationTree | null => {
      if (!explorationId) return null;
      return (
        useExplorationStore.getState().exploration.trees[explorationId] ?? null
      );
    },
    [],
  );

  const getConversation = useCallback(
    (
      explorationId: string | null | undefined,
      leafId: string | null | undefined,
    ): Conversation | null => {
      if (!explorationId || !leafId) return null;
      return (
        useExplorationStore.getState().exploration.conversations[
          explorationId
        ]?.[leafId] ?? null
      );
    },
    [],
  );

  const getProgress = useCallback(
    (explorationId: string | null | undefined): ExplorationProgress => {
      const tree = getTree(explorationId);
      if (!tree) return { explored: 0, total: 0, percentage: 0 };
      const total = countLeaves(tree);
      const explored = countExploredLeaves(tree);
      return {
        explored,
        total,
        percentage: total > 0 ? explored / total : 0,
      };
    },
    [getTree],
  );

  // ----- Leaf open/close -----

  /**
   * Optimistically set the active leaf, then ask the backend to stream
   * the leaf content. The backend's `conversation_opened` event will seed
   * the conversation if absent.
   */
  const openLeaf = useCallback(
    (explorationId: string, leafId: string) => {
      // Tag the action surface so SSE thinking events route to the leaf tab.
      dispatch(uiActions.lastActionTabSet('leaf'));
      dispatch(explorationActions.leafActivated(explorationId, leafId));

      // Trigger backend if no existing conversation. We compute the path
      // from root and call the navigate endpoint — the SSE flow takes over
      // from there.
      const state = useExplorationStore.getState();
      const tree = state.exploration.trees[explorationId];
      const existingConversation =
        state.exploration.conversations[explorationId]?.[leafId];
      if (!tree || existingConversation) return;

      const nodes = getPathTo(tree, leafId);
      if (!nodes) return;
      const targetPath = nodes.slice(1).map((n) => n.id);
      if (targetPath.length === 0) return;

      const sid = state.session.sessionId;
      if (!sid) return;

      dispatch(
        uiActions.thinkingStarted('retrieving', 'Inhalte werden geladen...'),
      );
      void explorationApiService
        .navigate(sid, explorationId, { targetPath })
        .catch((err) => {
          dispatch(uiActions.thinkingEnded());
          dispatch(
            uiActions.errorOccurred(
              'NAVIGATION_INVALID',
              err instanceof Error ? err.message : 'Navigation failed',
              true,
            ),
          );
        });
    },
    [dispatch],
  );

  const closeLeaf = useCallback(() => {
    dispatch(explorationActions.leafClosed());
  }, [dispatch]);

  // ----- Origin-gated derived state -----

  const chatIsThinking = useMemo(
    () =>
      isThinking &&
      (thinkingOriginTab === 'chat' || thinkingOriginTab === null),
    [isThinking, thinkingOriginTab],
  );
  const chatThinkingMessage = chatIsThinking ? thinkingMessage : null;

  const chatIsStreaming = useMemo(
    () =>
      isStreaming &&
      (streamingOriginTab === 'chat' || streamingOriginTab === null),
    [isStreaming, streamingOriginTab],
  );
  // Buffer/target are gated by origin tab (not isStreaming) so they keep
  // surfacing during the gap between stream_end and the chat_message commit.
  // The store now preserves both fields across STREAM_ENDED.
  const chatBufferOwned =
    streamingOriginTab === 'chat' || streamingOriginTab === null;
  const chatStreamBuffer = chatBufferOwned ? streamBuffer : '';
  const chatStreamingTargetType: StreamTargetType | null = chatBufferOwned
    ? (streamingTarget?.type ?? null)
    : null;

  const chatPendingChoice = useMemo(
    () =>
      pendingChoiceOriginTab === 'chat' || pendingChoiceOriginTab === null
        ? pendingChoice
        : null,
    [pendingChoice, pendingChoiceOriginTab],
  );
  const chatSuggestedQuestions = useMemo(
    () =>
      suggestedQuestionsOriginTab === 'chat' ||
      suggestedQuestionsOriginTab === null
        ? suggestedQuestions
        : [],
    [suggestedQuestions, suggestedQuestionsOriginTab],
  );

  const leafIsThinking = useMemo(
    () => isThinking && thinkingOriginTab === 'leaf',
    [isThinking, thinkingOriginTab],
  );
  const leafThinkingMessage = leafIsThinking ? thinkingMessage : null;

  const leafIsStreaming = useMemo(
    () => isStreaming && streamingOriginTab === 'leaf',
    [isStreaming, streamingOriginTab],
  );
  const leafBufferOwned = streamingOriginTab === 'leaf';
  const leafStreamBuffer = leafBufferOwned ? streamBuffer : '';
  const leafStreamingTargetType: StreamTargetType | null = leafBufferOwned
    ? (streamingTarget?.type ?? null)
    : null;

  const leafSuggestedQuestions = useMemo(
    () => (suggestedQuestionsOriginTab === 'leaf' ? suggestedQuestions : []),
    [suggestedQuestions, suggestedQuestionsOriginTab],
  );

  const leafTopicSwitchSuggestion = useMemo(() => {
    if (!topicSwitchSuggestion || !activeLeaf) return null;
    if (
      topicSwitchSuggestion.explorationId === activeLeaf.explorationId &&
      topicSwitchSuggestion.leafId === activeLeaf.leafId
    ) {
      return topicSwitchSuggestion;
    }
    return null;
  }, [topicSwitchSuggestion, activeLeaf]);

  /** True iff the closure prompt is for the currently-open leaf. */
  const leafClosureActive = useMemo(() => {
    if (!closurePrompt || !activeLeaf) return false;
    return (
      closurePrompt.explorationId === activeLeaf.explorationId &&
      closurePrompt.leafId === activeLeaf.leafId
    );
  }, [closurePrompt, activeLeaf]);

  // ----- Action wrappers -----

  /** Send a chat-tab message (adds user message to session immediately). */
  const sendChatMessage = useCallback(
    async (content: string) => {
      const userMessage: SessionMessage = {
        id: crypto.randomUUID(),
        type: 'user',
        content,
        timestamp: new Date().toISOString(),
      };
      dispatch(sessionActions.messageAdded(userMessage));
      await api.sendMessage(content);
    },
    [dispatch, api],
  );

  /** Send a leaf-tab follow-up — implicitly targets the active leaf. */
  const sendLeafMessage = useCallback(
    async (content: string) => {
      const active = useExplorationStore.getState().exploration.activeLeaf;
      if (!active) {
        throw new Error('sendLeafMessage: no active leaf');
      }
      await api.sendMessage(content, active.leafId, active.explorationId);
    },
    [api],
  );

  const acceptTopicSwitch = useCallback(
    (targetNodeId: string) => {
      const suggestion =
        useExplorationStore.getState().ui.topicSwitchSuggestion;
      dispatch(uiActions.topicSwitchCleared());
      if (!suggestion) return;
      // Mark the originating leaf explored before switching.
      void api.markExplored(suggestion.explorationId, suggestion.leafId);
      openLeaf(suggestion.explorationId, targetNodeId);
    },
    [api, dispatch, openLeaf],
  );

  const dismissTopicSwitch = useCallback(() => {
    dispatch(uiActions.topicSwitchCleared());
  }, [dispatch]);

  /** User chose "Weiter erkunden" — drop the closure prompt for this turn. */
  const dismissClosurePrompt = useCallback(() => {
    dispatch(uiActions.closurePromptCleared());
  }, [dispatch]);

  const markExplored = useCallback(
    (explorationId: string, leafId: string) =>
      api.markExplored(explorationId, leafId),
    [api],
  );

  const requestAnalysis = useCallback(
    (explorationId: string, leafId: string) =>
      api.requestAnalysis(explorationId, leafId),
    [api],
  );

  return {
    // Session
    sessionId,
    isConnected,
    error,
    clearError,
    mode,
    sessionMessages,

    // Multi-tree
    trees,
    getTree,
    getConversation,
    getProgress,

    // Active leaf
    activeLeaf,
    activeLeafTree,
    activeLeafNode,
    activeConversation,
    openLeaf,
    closeLeaf,

    // Chat-tab gated state
    chatIsThinking,
    chatThinkingMessage,
    chatIsStreaming,
    chatStreamBuffer,
    chatStreamingTargetType,
    chatPendingChoice,
    chatSuggestedQuestions,
    sendChatMessage,
    submitChoice: api.submitChoice,
    submitDirectionChoice: api.submitDirectionChoice,
    quickSummary,
    pendingDirections,

    // Leaf-tab gated state
    leafIsThinking,
    leafThinkingMessage,
    leafIsStreaming,
    leafStreamBuffer,
    leafStreamingTargetType,
    leafSuggestedQuestions,
    leafTopicSwitchSuggestion,
    leafClosureActive,
    sendLeafMessage,
    acceptTopicSwitch,
    dismissTopicSwitch,
    dismissClosurePrompt,

    // Per-tree actions
    markExplored,
    requestAnalysis,
    endExploration: api.endExploration,
    loadExploration: api.loadExploration,

    // Signals
    explorationPending,
    explorationReadyData,
    clearExplorationReady,

    // Connection
    connect,
    disconnect,
  };
}
