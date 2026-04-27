/**
 * useExploration Hook
 * Main hook combining store state, SSE, and API for exploration
 */

'use client';

import { useCallback, useEffect } from 'react';

import {
  explorationActions,
  selectActiveConversation,
  selectActiveTabId,
  selectAnalysisAvailable,
  selectBreadcrumb,
  selectCurrentPath,
  selectError,
  selectExplorationId,
  selectExplorationPending,
  selectExplorationReadyData,
  selectExplorationTabs,
  selectExploredCount,
  selectIsConnected,
  selectIsStreaming,
  selectIsThinking,
  selectMode,
  selectNavigation,
  selectPendingChoice,
  selectPendingChoiceOriginTab,
  selectPendingDirections,
  selectProgress,
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
  selectThinkingStage,
  selectTotalLeavesCount,
  selectTree,
  selectView,
  sessionActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import type { SessionMessage } from '@/modules/guided-exploration/types';
import {
  buildBreadcrumb,
  getViewFromNodeId,
} from '@/modules/guided-exploration/utils';
import { useExplorationApi } from './use-exploration-api';
import { useFirebaseSummaries } from './use-firebase-summaries';
import { useSSE } from './use-sse';

export interface UseExplorationOptions {
  /** Session ID to restore (optional) */
  initialSessionId?: string;
  /** Auto-create session if none exists */
  autoCreateSession?: boolean;
}

/**
 * Main hook for guided exploration functionality
 * Combines state, SSE connection, and API methods
 */
export function useExploration(options: UseExplorationOptions = {}) {
  const { initialSessionId, autoCreateSession = false } = options;

  const dispatch = useExplorationStore((s) => s.dispatch);

  // State selectors
  const sessionId = useExplorationStore(selectSessionId);
  const explorationId = useExplorationStore(selectExplorationId);
  const isConnected = useExplorationStore(selectIsConnected);
  const mode = useExplorationStore(selectMode);
  const view = useExplorationStore(selectView);
  const tree = useExplorationStore(selectTree);
  const navigation = useExplorationStore(selectNavigation);
  const currentPath = useExplorationStore(selectCurrentPath);
  const breadcrumb = useExplorationStore(selectBreadcrumb);
  const activeConversation = useExplorationStore(selectActiveConversation);
  const analysisAvailable = useExplorationStore(selectAnalysisAvailable);
  const isStreaming = useExplorationStore(selectIsStreaming);
  const streamBuffer = useExplorationStore(selectStreamBuffer);
  const streamingTarget = useExplorationStore(selectStreamingTarget);
  const streamingOriginTab = useExplorationStore(selectStreamingOriginTab);

  const thinkingStage = useExplorationStore(selectThinkingStage);
  const thinkingMessage = useExplorationStore(selectThinkingMessage);
  const isThinking = useExplorationStore(selectIsThinking);
  const thinkingOriginTab = useExplorationStore(selectThinkingOriginTab);
  const pendingChoice = useExplorationStore(selectPendingChoice);
  const pendingChoiceOriginTab = useExplorationStore(
    selectPendingChoiceOriginTab,
  );
  const quickSummary = useExplorationStore(selectQuickSummary);
  const error = useExplorationStore(selectError);
  const exploredCount = useExplorationStore(selectExploredCount);
  const totalCount = useExplorationStore(selectTotalLeavesCount);
  const progress = useExplorationStore(selectProgress);
  const sessionMessages = useExplorationStore(selectSessionMessages);
  const explorationPending = useExplorationStore(selectExplorationPending);
  const explorationReadyData = useExplorationStore(selectExplorationReadyData);
  const suggestedQuestions = useExplorationStore(selectSuggestedQuestions);
  const suggestedQuestionsOriginTab = useExplorationStore(
    selectSuggestedQuestionsOriginTab,
  );
  const topicSwitchSuggestion = useExplorationStore(
    (s) => s.ui.topicSwitchSuggestion,
  );
  const pendingDirections = useExplorationStore(selectPendingDirections);
  const activeTabId = useExplorationStore(selectActiveTabId);
  const explorationTabs = useExplorationStore(selectExplorationTabs);

  // SSE connection
  const { connect, disconnect } = useSSE({ autoConnect: true });

  // API methods
  const api = useExplorationApi();

  // Firebase summaries
  const { summaries, loading: summariesLoading } = useFirebaseSummaries();

  // Initialize session
  useEffect(() => {
    const initSession = async () => {
      if (initialSessionId) {
        // Restore existing session
        // Note: SSE auto-connect will handle connection when sessionId is set in store
        try {
          await api.resumeSession(initialSessionId);
        } catch (e) {
          console.error('Failed to restore session:', e);
          if (autoCreateSession) {
            await api.createSession();
          }
        }
      } else if (autoCreateSession && !sessionId) {
        // Create new session
        // Note: SSE auto-connect will handle connection when sessionId is set in store
        await api.createSession();
      }
    };

    initSession();
    // Note: api and connect are stable (created with useCallback), sessionId is intentionally
    // not included to prevent re-running when session is created (would cause infinite loop)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSessionId, autoCreateSession]);

  // Clear error
  const clearError = useCallback(() => {
    dispatch(uiActions.errorCleared());
  }, [dispatch]);

  // Clear exploration ready data after navigation
  const clearExplorationReady = useCallback(() => {
    dispatch(explorationActions.readyCleared());
  }, [dispatch]);

  // Send chat message (adds user message to store immediately)
  const sendChatMessage = useCallback(
    async (content: string) => {
      // Add user message to store immediately
      const userMessage: SessionMessage = {
        id: crypto.randomUUID(),
        type: 'user',
        content,
        timestamp: new Date().toISOString(),
      };
      dispatch(sessionActions.messageAdded(userMessage));

      // Send to backend via existing API
      await api.sendMessage(content);
    },
    [dispatch, api],
  );

  /**
   * Optimistic navigation helper
   * Updates UI immediately, then syncs with backend
   */
  const navigateOptimistically = useCallback(
    (newPath: string[]) => {
      if (!tree || !explorationId) return;

      const targetId = newPath[newPath.length - 1] ?? null;
      const newView = getViewFromNodeId(tree, targetId);
      const newBreadcrumb = buildBreadcrumb(tree, newPath);
      const navigationState = {
        explorationId,
        currentPath: newPath,
        breadcrumb: newBreadcrumb,
      };

      // Optimistically update UI based on view type
      if (newView === 'root') {
        dispatch(explorationActions.navigatedToRoot(navigationState));
      } else if (newView === 'branch') {
        dispatch(explorationActions.navigatedToBranch(navigationState));
      } else if (newView === 'leaf' && targetId) {
        // For leaf navigation, navigate immediately with empty conversation
        // Backend will stream the content
        const emptyConversation = {
          leafId: targetId,
          messages: [],
          hasSummary: false,
        };

        dispatch(
          explorationActions.navigatedToLeaf(
            targetId,
            emptyConversation,
            navigationState,
            false, // analysisAvailable - will be updated by backend
          ),
        );
      }

      // Sync with backend in background
      void api.navigate(newPath);
    },
    [tree, explorationId, dispatch, api],
  );

  // Navigation helpers with optimistic updates
  const goToRoot = useCallback(() => {
    navigateOptimistically([]);
  }, [navigateOptimistically]);

  const goToTopic = useCallback(
    (topicId: string) => {
      navigateOptimistically([topicId]);
    },
    [navigateOptimistically],
  );

  const goToSubtopic = useCallback(
    (topicId: string, subtopicId: string) => {
      // Navigate optimistically - UI updates immediately, backend streams content
      navigateOptimistically([topicId, subtopicId]);
    },
    [navigateOptimistically],
  );

  const goBack = useCallback(() => {
    if (currentPath.length > 0) {
      navigateOptimistically(currentPath.slice(0, -1));
    }
  }, [currentPath, navigateOptimistically]);

  return {
    // Session
    sessionId,
    explorationId,
    isConnected,

    // Mode & View
    mode,
    view,

    // Tree & Navigation
    tree,
    navigation,
    currentPath,
    breadcrumb,

    // Conversation
    activeConversation,
    analysisAvailable,

    // Streaming
    isStreaming,
    streamBuffer,
    streamingTarget,
    streamingOriginTab,

    // Thinking
    thinkingStage,
    thinkingMessage,
    isThinking,
    thinkingOriginTab,

    // Choice
    pendingChoice,
    pendingChoiceOriginTab,
    pendingDirections,
    quickSummary,

    // Session Messages
    sessionMessages,

    // Suggested Questions
    suggestedQuestions,
    suggestedQuestionsOriginTab,

    // Topic Switch
    topicSwitchSuggestion,
    acceptTopicSwitch: useCallback(
      (targetNodeId: string) => {
        if (activeConversation?.leafId) {
          api.markExplored(activeConversation.leafId);
        }
        dispatch(uiActions.topicSwitchCleared());
        navigateOptimistically([targetNodeId]);
      },
      [activeConversation, api, dispatch, navigateOptimistically],
    ),
    dismissTopicSwitch: useCallback(() => {
      dispatch(uiActions.topicSwitchCleared());
    }, [dispatch]),

    // Tabs
    activeTabId,
    explorationTabs,
    switchTab: useCallback(
      (tabId: 'chat' | string) => {
        dispatch(sessionActions.tabSwitched(tabId));
      },
      [dispatch],
    ),

    // Exploration Pending State
    explorationPending,
    explorationReadyData,
    clearExplorationReady,

    // Progress
    summaries,
    summariesLoading,
    exploredCount,
    totalCount,
    progress,

    // Error
    error,
    clearError,

    // API Actions
    createSession: api.createSession,
    sendMessage: api.sendMessage,
    sendChatMessage,
    loadExploration: api.loadExploration,
    submitChoice: api.submitChoice,
    submitDirectionChoice: api.submitDirectionChoice,
    requestAnalysis: api.requestAnalysis,
    endExploration: api.endExploration,
    requestExport: api.requestExport,
    getExportUrl: api.getExportUrl,

    // Navigation Actions
    navigate: api.navigate,
    navigateOptimistically,
    goToRoot,
    goToTopic,
    goToSubtopic,
    goBack,

    // Exploration tracking
    markExplored: api.markExplored,

    // Connection
    connect,
    disconnect,
  };
}
