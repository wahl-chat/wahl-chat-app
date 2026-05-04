'use client';

import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';

import { ExplorationChatView } from '@/modules/guided-exploration/components/chat/exploration-chat-view';
import { LeafSidebar } from '@/modules/guided-exploration/components/chat/leaf-sidebar';
import { ErrorBanner } from '@/modules/guided-exploration/components/shared';
import { ExplorationLoading } from '@/modules/guided-exploration/components/shared/exploration-loading';
import { useExploration } from '@/modules/guided-exploration/hooks';
import {
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import { findNode } from '@/modules/guided-exploration/utils/tree-helpers';

interface StudyExplorationWrapperProps {
  /** The chat session ID from the study API */
  chatId: string;
  /** Called when the exploration is ready */
  onReady?: () => void;
  /**
   * The label of the participant's assigned study topic
   * (e.g. "Klimaschutz"). When set, the empty-view topic buttons are
   * restricted to this topic only.
   */
  studyTopicLabel?: string;
}

/**
 * Study task exploration view (v3).
 *
 * Same shape as {@link import('@/modules/guided-exploration/components/layout/exploration-main').ExplorationMain}:
 * a single chat surface with inline tree cards and a right-side
 * {@link LeafSidebar}. The study-specific behaviours are:
 *  - empty view restricted to a single assigned topic via `studyTopicLabel`
 *  - direction selection requires `minDirections={2}`
 *  - signals readiness once the SSE connection is up
 *
 * The previous URL-driven `?exploration=` / `?path=` flow is gone — the
 * sidebar handles the per-leaf chat without route changes. `?leaf=<id>`
 * deep links still work and open the matching tree's leaf sidebar.
 */
export function StudyExplorationWrapper({
  chatId,
  onReady,
  studyTopicLabel,
}: StudyExplorationWrapperProps) {
  const searchParams = useSearchParams();
  const hasNotifiedReady = useRef(false);
  const hasOpenedDeepLink = useRef(false);
  const dispatch = useExplorationStore((s) => s.dispatch);

  const {
    isConnected,
    error,
    mode,
    sessionMessages,

    trees,
    activeLeaf,
    activeLeafNode,
    activeConversation,
    openLeaf,
    closeLeaf,

    chatIsThinking,
    chatThinkingMessage,
    chatStreamBuffer,
    chatIsStreaming,
    chatStreamingTargetType,
    chatPendingChoice,
    chatSuggestedQuestions,
    sendChatMessage,
    submitChoice,
    submitDirectionChoice,

    leafIsThinking,
    leafThinkingMessage,
    leafStreamBuffer,
    leafIsStreaming,
    leafStreamingTargetType,
    leafSuggestedQuestions,
    leafTopicSwitchSuggestion,
    sendLeafMessage,
    acceptTopicSwitch,
    dismissTopicSwitch,
    markExplored,

    explorationPending,
    explorationReadyData,
    clearExplorationReady,
  } = useExploration({
    initialSessionId: chatId,
    autoCreateSession: false,
  });

  useEffect(() => {
    if (isConnected && !hasNotifiedReady.current) {
      hasNotifiedReady.current = true;
      onReady?.();
    }
  }, [isConnected, onReady]);

  // Clear the one-shot exploration_ready signal once observed.
  useEffect(() => {
    if (explorationReadyData) {
      clearExplorationReady();
    }
  }, [explorationReadyData, clearExplorationReady]);

  const pendingTree = useMemo(
    () => (explorationPending ? (trees[trees.length - 1] ?? null) : null),
    [explorationPending, trees],
  );

  // Deep link: ?leaf=<id> opens the matching leaf sidebar once the leaf
  // can be resolved to a tree. Runs once per mount.
  const deepLinkLeaf = searchParams.get('leaf');
  const deepLinkExplorationId = useMemo(() => {
    if (!deepLinkLeaf) return null;
    for (const t of trees) {
      if (findNode(t, deepLinkLeaf)) return t.explorationId;
    }
    return null;
  }, [deepLinkLeaf, trees]);

  useEffect(() => {
    if (!deepLinkLeaf || !deepLinkExplorationId || hasOpenedDeepLink.current) {
      return;
    }
    hasOpenedDeepLink.current = true;
    openLeaf(deepLinkExplorationId, deepLinkLeaf);
  }, [deepLinkLeaf, deepLinkExplorationId, openLeaf]);

  const handleDismissError = useCallback(() => {
    dispatch(uiActions.errorCleared());
  }, [dispatch]);

  if (!isConnected && mode === 'idle') {
    return <ExplorationLoading message="Verbindung wird hergestellt..." />;
  }

  const isLeafOpen = !!activeLeaf;

  return (
    <div
      id="main-content"
      tabIndex={-1}
      className="flex flex-1 flex-col overflow-hidden focus:outline-none"
    >
      {error && (
        <ErrorBanner message={error.message} onDismiss={handleDismissError} />
      )}

      <ExplorationChatView
        messages={sessionMessages}
        pendingChoice={chatPendingChoice}
        isThinking={chatIsThinking}
        thinkingMessage={chatThinkingMessage}
        streamBuffer={chatStreamBuffer}
        isStreaming={chatIsStreaming}
        streamingTargetType={chatStreamingTargetType}
        tree={pendingTree}
        explorationPending={explorationPending}
        suggestedQuestions={chatSuggestedQuestions}
        studyTopicLabel={studyTopicLabel}
        minDirections={2}
        onSendMessageAction={sendChatMessage}
        onSubmitChoiceAction={submitChoice}
        onDirectionChoiceAction={submitDirectionChoice}
        onOpenLeafAction={openLeaf}
        deepLinkExplorationId={deepLinkExplorationId}
        deepLinkLeafId={deepLinkLeaf}
      />

      <LeafSidebar
        open={isLeafOpen}
        leafNode={activeLeafNode}
        conversation={activeConversation}
        isThinking={leafIsThinking}
        thinkingMessage={leafThinkingMessage}
        isStreaming={leafIsStreaming}
        streamBuffer={leafStreamBuffer}
        streamingTargetType={leafStreamingTargetType}
        topicSwitchSuggestion={leafTopicSwitchSuggestion}
        suggestedQuestions={leafSuggestedQuestions}
        hideAspectView
        showMissingPartiesPlaceholder
        onSendMessage={sendLeafMessage}
        onAcceptSwitch={
          leafTopicSwitchSuggestion
            ? () => acceptTopicSwitch(leafTopicSwitchSuggestion.targetNodeId)
            : undefined
        }
        onDismissSwitch={dismissTopicSwitch}
        onMarkExplored={
          activeLeaf
            ? () => {
                void markExplored(activeLeaf.explorationId, activeLeaf.leafId);
                closeLeaf();
              }
            : undefined
        }
        onClose={closeLeaf}
      />
    </div>
  );
}
