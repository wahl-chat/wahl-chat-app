'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';

import { ExplorationChatView } from '@/modules/guided-exploration/components/chat/exploration-chat-view';
import { ExplorationFullView } from '@/modules/guided-exploration/components/exploration-view';
import { ExplorationLoading } from '@/modules/guided-exploration/components/shared/exploration-loading';
import { useExploration } from '@/modules/guided-exploration/hooks';
import {
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';

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
  const hasLoadedExploration = useRef(false);
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
  } = useExploration({
    initialSessionId,
    autoCreateSession: !initialSessionId,
  });

  // Debug: log streamingTarget in exploration-main
  console.log('=== [ExplorationMain] RENDER ===');
  console.log('[ExplorationMain] streamingTarget:', streamingTarget);
  console.log('[ExplorationMain] isStreaming:', isStreaming);
  console.log('[ExplorationMain] streamBuffer length:', streamBuffer?.length);

  // Build URL with path query param
  const buildExplorationUrl = useCallback(
    (path: string[]) => {
      const base = `/${contextId}/explore/${sessionId}/explorations/${initialExplorationId}`;
      if (path.length === 0) {
        return base;
      }
      return `${base}?path=${path.join(',')}`;
    },
    [contextId, sessionId, initialExplorationId],
  );

  // Navigation handlers that update URL
  const handleNavigateToRoot = useCallback(() => {
    if (sessionId && initialExplorationId) {
      router.push(buildExplorationUrl([]));
    }
  }, [router, sessionId, initialExplorationId, buildExplorationUrl]);

  const handleNavigateToNode = useCallback(
    (nodeId: string) => {
      if (sessionId && initialExplorationId) {
        router.push(buildExplorationUrl([nodeId]));
      }
    },
    [router, sessionId, initialExplorationId, buildExplorationUrl],
  );

  const handleBack = useCallback(() => {
    if (currentPath.length > 0 && sessionId && initialExplorationId) {
      router.push(buildExplorationUrl(currentPath.slice(0, -1)));
    }
  }, [
    router,
    currentPath,
    sessionId,
    initialExplorationId,
    buildExplorationUrl,
  ]);

  // Navigate to session URL when a new session is created
  useEffect(() => {
    if (sessionId && !initialSessionId && !hasNavigated.current) {
      hasNavigated.current = true;
      router.replace(`/${contextId}/explore/${sessionId}`);
    }
  }, [sessionId, initialSessionId, contextId, router]);

  // Clear thinking state when returning to chat mode (no explorationId in URL)
  useEffect(() => {
    if (!initialExplorationId) {
      dispatch(uiActions.thinkingEnded());
      hasLoadedExploration.current = false;
      lastNavigatedPath.current = null;
    }
  }, [initialExplorationId, dispatch]);

  // Load exploration when navigating to /explore/[sessionId]/explorations/[explorationId]
  useEffect(() => {
    if (initialExplorationId && isConnected && !hasLoadedExploration.current) {
      hasLoadedExploration.current = true;
      loadExploration(initialExplorationId).catch(() => {
        // Error already dispatched to UI state
      });
    }
  }, [initialExplorationId, isConnected, loadExploration]);

  // Navigate to path from URL when it changes (optimistic)
  useEffect(() => {
    if (initialExplorationId && isConnected && tree) {
      const urlPathStr = initialPath.join(',');

      // Skip if we've already navigated to this path
      if (lastNavigatedPath.current === urlPathStr) {
        return;
      }

      const currentPathStr = currentPath.join(',');

      if (urlPathStr !== currentPathStr) {
        // Track that we're navigating to this path
        lastNavigatedPath.current = urlPathStr;
        // URL path differs from store path, navigate optimistically
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

  // Auto-navigate to exploration when ready
  useEffect(() => {
    if (explorationReadyData && sessionId) {
      const { explorationId } = explorationReadyData;
      const targetUrl = `/${contextId}/explore/${sessionId}/explorations/${explorationId}`;
      clearExplorationReady();
      router.push(targetUrl);
    }
  }, [
    explorationReadyData,
    sessionId,
    contextId,
    router,
    clearExplorationReady,
  ]);

  // Navigate to exploration URL instead of loading directly
  const handleEnterExploration = useCallback(
    (explorationId: string) => {
      if (sessionId) {
        router.push(
          `/${contextId}/explore/${sessionId}/explorations/${explorationId}`,
        );
      }
    },
    [contextId, sessionId, router],
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

  // Show loading while waiting for tree (after user starts exploration)
  if (!tree && mode === 'exploring') {
    return <ExplorationLoading message="Themenbaum wird erstellt..." />;
  }

  // EXPLORATION MODE: When explorationId is in URL and tree is loaded
  if (initialExplorationId && tree && sessionId) {
    return (
      <ExplorationFullView
        contextId={contextId}
        sessionId={sessionId}
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
        onSendMessage={(msg) => sendMessage(msg, activeConversation?.leafId)}
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
    );
  }

  // CHAT MODE: Regular chat with exploration entry cards
  return (
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
      onEnterExplorationAction={handleEnterExploration}
    />
  );
}
