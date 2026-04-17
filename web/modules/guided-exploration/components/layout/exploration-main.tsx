'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';

import { ExplorationChatView } from '@/modules/guided-exploration/components/chat/exploration-chat-view';
import { ExplorationFullView } from '@/modules/guided-exploration/components/exploration-view';
import { ExplorationLoading } from '@/modules/guided-exploration/components/shared/exploration-loading';
import { useExploration } from '@/modules/guided-exploration/hooks';
import {
  sessionActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';

import { EXPLORATION_PANEL_ID, ExplorationTabBar } from './exploration-tab-bar';

interface ExplorationMainProps {
  /** Session ID from URL (when navigating to /explore/[sessionId]) */
  initialSessionId?: string;
  /** Exploration ID from URL (when navigating to /explore/[sessionId]/explorations/[explorationId]) */
  initialExplorationId?: string;
}

export function ExplorationMain({
  initialSessionId,
  initialExplorationId,
}: ExplorationMainProps) {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const contextId = params.contextId as string;
  const hasNavigated = useRef(false);
  const loadedExplorations = useRef<Set<string>>(new Set());
  const lastNavigatedPath = useRef<string | null>(null);
  const dispatch = useExplorationStore((s) => s.dispatch);

  // Get path from URL query params
  const urlPath = searchParams.get('path');
  const initialPath = useMemo(
    () => (urlPath ? urlPath.split(',').filter(Boolean) : []),
    [urlPath],
  );

  const {
    mode,
    view,
    tree,
    currentPath,
    breadcrumb,
    isConnected,
    error,
    navigateOptimistically,
    summaries,
    activeConversation,
    analysisAvailable,
    isThinking,
    thinkingMessage,
    sendMessage,
    sendChatMessage,
    loadExploration,
    submitChoice,
    submitDirectionChoice,
    requestAnalysis,
    markExplored,
    sessionMessages,
    pendingChoice,
    streamBuffer,
    streamingTarget,
    isStreaming,
    sessionId,
    explorationPending,
    explorationReadyData,
    clearExplorationReady,
    suggestedQuestions,
    topicSwitchSuggestion,
    acceptTopicSwitch,
    dismissTopicSwitch,
    // Tabs
    activeTabId,
    explorationTabs,
  } = useExploration({
    initialSessionId,
    autoCreateSession: !initialSessionId,
  });

  // Build URL with path query param
  const buildExplorationUrl = useCallback(
    (explorationId: string, path: string[]) => {
      const base = `/${contextId}/explore/${sessionId}/explorations/${explorationId}`;
      if (path.length === 0) {
        return base;
      }
      return `${base}?path=${path.join(',')}`;
    },
    [contextId, sessionId],
  );

  // Navigation handlers
  const activeExplorationId =
    activeTabId !== 'chat' ? activeTabId : initialExplorationId;

  const handleNavigateToRoot = useCallback(() => {
    if (sessionId && activeExplorationId) {
      router.push(buildExplorationUrl(activeExplorationId, []));
    }
  }, [router, sessionId, activeExplorationId, buildExplorationUrl]);

  const handleNavigateToNode = useCallback(
    (nodeId: string) => {
      if (sessionId && activeExplorationId) {
        router.push(buildExplorationUrl(activeExplorationId, [nodeId]));
      }
    },
    [router, sessionId, activeExplorationId, buildExplorationUrl],
  );

  const handleBack = useCallback(() => {
    if (currentPath.length > 0 && sessionId && activeExplorationId) {
      router.push(
        buildExplorationUrl(activeExplorationId, currentPath.slice(0, -1)),
      );
    }
  }, [
    router,
    currentPath,
    sessionId,
    activeExplorationId,
    buildExplorationUrl,
  ]);

  // Navigate to session URL when a new session is created
  useEffect(() => {
    if (sessionId && !initialSessionId && !hasNavigated.current) {
      hasNavigated.current = true;
      router.replace(`/${contextId}/explore/${sessionId}`);
    }
  }, [sessionId, initialSessionId, contextId, router]);

  // Clear thinking state when returning to chat mode
  useEffect(() => {
    if (!initialExplorationId) {
      dispatch(uiActions.thinkingEnded());
      lastNavigatedPath.current = null;
    }
  }, [initialExplorationId, dispatch]);

  // Load exploration when navigating to it via URL (skip if already loaded)
  useEffect(() => {
    if (
      initialExplorationId &&
      isConnected &&
      !loadedExplorations.current.has(initialExplorationId)
    ) {
      loadedExplorations.current.add(initialExplorationId);
      loadExploration(initialExplorationId).catch(() => {
        // Remove from loaded set so it can be retried
        loadedExplorations.current.delete(initialExplorationId);
      });
    }
  }, [initialExplorationId, isConnected, loadExploration]);

  // Navigate to path from URL when it changes
  useEffect(() => {
    if (initialExplorationId && isConnected && tree) {
      const urlPathStr = initialPath.join(',');
      if (lastNavigatedPath.current === urlPathStr) return;
      const currentPathStr = currentPath.join(',');
      if (urlPathStr !== currentPathStr) {
        lastNavigatedPath.current = urlPathStr;
        navigateOptimistically(initialPath);
      }
    }
  }, [
    initialExplorationId,
    isConnected,
    tree,
    initialPath,
    currentPath,
    navigateOptimistically,
  ]);

  // Clear exploration ready data
  useEffect(() => {
    if (explorationReadyData) {
      clearExplorationReady();
    }
  }, [explorationReadyData, clearExplorationReady]);

  // Tab switching: when user clicks an exploration tab, navigate to its URL
  const handleTabSwitch = useCallback(
    (tabId: 'chat' | string) => {
      // Save current path before switching
      dispatch(sessionActions.tabSwitched(tabId, currentPath));

      if (tabId === 'chat') {
        if (sessionId) {
          router.push(`/${contextId}/explore/${sessionId}`);
        }
      } else {
        if (sessionId) {
          // Restore last path for the target exploration
          const targetTab = explorationTabs[tabId];
          const restoredPath = targetTab?.lastPath ?? [];
          const pathParam =
            restoredPath.length > 0 ? `?path=${restoredPath.join(',')}` : '';
          router.push(
            `/${contextId}/explore/${sessionId}/explorations/${tabId}${pathParam}`,
          );
        }
      }
    },
    [dispatch, sessionId, contextId, router, currentPath, explorationTabs],
  );

  const handleTabClose = useCallback(
    (explorationId: string) => {
      dispatch(sessionActions.explorationTabRemoved(explorationId));
      // If closing the active tab, navigate to chat
      if (activeTabId === explorationId && sessionId) {
        router.push(`/${contextId}/explore/${sessionId}`);
      }
    },
    [dispatch, activeTabId, sessionId, contextId, router],
  );

  // Enter exploration from chat card — ensure tab exists before switching
  const handleEnterExploration = useCallback(
    (expId: string) => {
      if (!explorationTabs[expId]) {
        // Find the exploration query from session messages
        const startMsg = sessionMessages.find(
          (m) => m.type === 'exploration_start' && m.explorationId === expId,
        );
        const query = startMsg?.explorationQuery || 'Erkundung';
        const label = query.length > 30 ? `${query.slice(0, 27)}...` : query;
        const tabCount = Object.keys(explorationTabs).length;
        dispatch(
          sessionActions.explorationTabAdded(expId, label, tabCount % 6),
        );
      }
      handleTabSwitch(expId);
    },
    [handleTabSwitch, explorationTabs, sessionMessages, dispatch],
  );

  // Show error state
  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-4">
        <p className="text-destructive">{error.message}</p>
      </div>
    );
  }

  // Show loading while connecting
  if (!isConnected && mode === 'idle') {
    return <ExplorationLoading message="Verbindung wird hergestellt..." />;
  }

  // Determine what to show in the content area
  const isExplorationActive = !!initialExplorationId && !!sessionId;
  const isExplorationLoaded = isExplorationActive && !!tree;
  const isExplorationLoading = isExplorationActive && !tree;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Tab bar */}
      <ExplorationTabBar
        activeTabId={activeTabId}
        explorationTabs={explorationTabs}
        isInExploration={isExplorationActive}
        onTabSwitch={handleTabSwitch}
        onTabClose={handleTabClose}
      />

      {/* Tab panel — holds whichever view matches the active tab */}
      <div
        id={EXPLORATION_PANEL_ID}
        role="tabpanel"
        aria-labelledby={`exploration-tab-${activeTabId}`}
        className="flex flex-1 flex-col overflow-hidden focus:outline-none"
      >
        {/* Loading state when switching to an exploration */}
        {isExplorationLoading && (
          <ExplorationLoading message="Erkundung wird geladen..." />
        )}

        {/* Exploration content */}
        {isExplorationLoaded ? (
          <ExplorationFullView
            tree={tree}
            view={view}
            currentPath={currentPath}
            breadcrumb={breadcrumb}
            activeConversation={activeConversation}
            summaries={summaries}
            analysisAvailable={analysisAvailable}
            isThinking={isThinking}
            thinkingMessage={thinkingMessage}
            isStreaming={isStreaming}
            streamBuffer={streamBuffer}
            streamingTargetType={streamingTarget?.type}
            onNavigate={handleNavigateToNode}
            onGoToRoot={handleNavigateToRoot}
            onSubtopicSelect={handleNavigateToNode}
            onBack={handleBack}
            onSendMessage={(msg) =>
              sendMessage(msg, activeConversation?.leafId)
            }
            onRequestAnalysis={() => {
              if (activeConversation?.leafId) {
                requestAnalysis(activeConversation.leafId);
              }
            }}
            onMarkExplored={markExplored}
            suggestedQuestions={suggestedQuestions}
            topicSwitchSuggestion={topicSwitchSuggestion}
            onAcceptSwitch={acceptTopicSwitch}
            onDismissSwitch={dismissTopicSwitch}
          />
        ) : !isExplorationLoading ? (
          <ExplorationChatView
            messages={sessionMessages}
            pendingChoice={pendingChoice}
            isThinking={isThinking}
            thinkingMessage={thinkingMessage}
            streamBuffer={streamBuffer}
            isStreaming={isStreaming}
            streamingTargetType={streamingTarget?.type}
            tree={tree}
            explorationPending={explorationPending}
            suggestedQuestions={suggestedQuestions}
            onSendMessageAction={sendChatMessage}
            onSubmitChoiceAction={submitChoice}
            onDirectionChoiceAction={submitDirectionChoice}
            onEnterExplorationAction={handleEnterExploration}
          />
        ) : null}
      </div>
    </div>
  );
}
