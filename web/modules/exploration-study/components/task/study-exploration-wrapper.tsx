'use client';

import {
  ExplorationChatView,
  ExplorationFullView,
  ExplorationLoading,
} from '@/modules/guided-exploration/components';
import { KnowledgeBaseDebug } from '@/modules/guided-exploration/components/debug/knowledge-base-debug';
import { ErrorBanner } from '@/modules/guided-exploration/components/shared';
import { useExploration } from '@/modules/guided-exploration/hooks';
import {
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import { useCallback, useEffect, useRef } from 'react';

interface StudyExplorationWrapperProps {
  /** The chat session ID from the study API */
  chatId: string;
  /** Initial exploration ID to load (for resuming) */
  initialExplorationId?: string | null;
  /** Called when the exploration is ready */
  onReady?: () => void;
}

/**
 * Wrapper for ExplorationMain that works within the study context.
 * Uses internal state for navigation instead of URL routing.
 */
export function StudyExplorationWrapper({
  chatId,
  initialExplorationId,
  onReady,
}: StudyExplorationWrapperProps) {
  const hasNotifiedReady = useRef(false);
  const explorationIdRef = useRef<string | null>(initialExplorationId ?? null);
  const hasLoadedInitial = useRef(false);
  const dispatch = useExplorationStore((s) => s.dispatch);

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
  } = useExploration({
    initialSessionId: chatId,
    autoCreateSession: false,
  });

  // Notify when connected and ready
  useEffect(() => {
    if (isConnected && !hasNotifiedReady.current) {
      hasNotifiedReady.current = true;
      onReady?.();
    }
  }, [isConnected, onReady]);

  // Load initial exploration if provided (for resuming a session)
  useEffect(() => {
    if (isConnected && initialExplorationId && !hasLoadedInitial.current) {
      hasLoadedInitial.current = true;
      loadExploration(initialExplorationId).catch(() => {
        // Error already dispatched to UI state
      });
    }
  }, [isConnected, initialExplorationId, loadExploration]);

  // Handle exploration ready - load it directly instead of navigating
  useEffect(() => {
    if (explorationReadyData && !hasLoadedInitial.current) {
      const { explorationId } = explorationReadyData;
      explorationIdRef.current = explorationId;
      clearExplorationReady();
      loadExploration(explorationId).catch(() => {
        // Error already dispatched to UI state
      });
    }
  }, [explorationReadyData, clearExplorationReady, loadExploration]);

  // Internal navigation handlers (no URL changes)
  const handleNavigateToRoot = useCallback(() => {
    navigateOptimistically([]);
  }, [navigateOptimistically]);

  const handleNavigateToTopic = useCallback(
    (topicId: string) => {
      navigateOptimistically([topicId]);
    },
    [navigateOptimistically],
  );

  const handleNavigateToSubtopic = useCallback(
    (nodeId: string) => {
      navigateOptimistically([...currentPath, nodeId]);
    },
    [navigateOptimistically, currentPath],
  );

  const handleBack = useCallback(() => {
    if (currentPath.length > 0) {
      navigateOptimistically(currentPath.slice(0, -1));
    }
  }, [currentPath, navigateOptimistically]);

  const handleEnterExploration = useCallback(
    (explorationId: string) => {
      explorationIdRef.current = explorationId;
      loadExploration(explorationId).catch(() => {
        // Error already dispatched to UI state
      });
    },
    [loadExploration],
  );

  const handleDismissError = useCallback(() => {
    dispatch(uiActions.errorCleared());
  }, [dispatch]);

  // Show loading while connecting
  if (!isConnected && mode === 'idle') {
    return <ExplorationLoading message="Verbindung wird hergestellt..." />;
  }

  // Show loading while waiting for tree (after user starts exploration)
  if (!tree && mode === 'exploring') {
    return <ExplorationLoading message="Themenbaum wird erstellt..." />;
  }

  // EXPLORATION MODE: When tree is loaded
  if (tree && sessionId && explorationIdRef.current) {
    return (
      <>
        {error && (
          <ErrorBanner message={error.message} onDismiss={handleDismissError} />
        )}
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
          onNavigate={handleNavigateToTopic}
          onGoToRoot={handleNavigateToRoot}
          onSubtopicSelect={handleNavigateToSubtopic}
          onBack={handleBack}
          onSendMessage={(msg) => sendMessage(msg, activeConversation?.leafId)}
          onRequestAnalysis={() => {
            if (activeConversation?.leafId) {
              requestAnalysis(activeConversation.leafId);
            }
          }}
          onMarkExplored={markExplored}
          suggestedQuestions={suggestedQuestions}
        />
        <KnowledgeBaseDebug
          sessionId={sessionId}
          explorationId={explorationIdRef.current}
          tree={tree}
        />
      </>
    );
  }

  // CHAT MODE: Regular chat with exploration entry cards
  return (
    <>
      {error && (
        <ErrorBanner message={error.message} onDismiss={handleDismissError} />
      )}
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
    </>
  );
}
