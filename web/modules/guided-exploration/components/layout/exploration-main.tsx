'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef } from 'react';

import { ExplorationChatView } from '@/modules/guided-exploration/components/chat/exploration-chat-view';
import { LeafCloseAnnouncer } from '@/modules/guided-exploration/components/chat/leaf-close-announcer';
import { LeafSidebar } from '@/modules/guided-exploration/components/chat/leaf-sidebar';
import { ExplorationLoading } from '@/modules/guided-exploration/components/shared/exploration-loading';
import {
  useExploration,
  useLeafBackInterception,
  useLeafCloseFlow,
} from '@/modules/guided-exploration/hooks';
import { findNode } from '@/modules/guided-exploration/utils/tree-helpers';

interface ExplorationMainProps {
  /** Session ID from URL (when navigating to /explore/[sessionId]) */
  initialSessionId?: string;
}

/**
 * v3 entry point: a single chat surface in which exploration trees render
 * inline as collapsible disclosures. A leaf opens in a right-side
 * {@link LeafSidebar} that hosts the per-leaf chat. There are no longer
 * any per-exploration routes or tabs.
 */
export function ExplorationMain({ initialSessionId }: ExplorationMainProps) {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const contextId = params.contextId as string;
  const hasNavigated = useRef(false);
  const hasOpenedDeepLink = useRef(false);

  const {
    sessionId,
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
    leafClosureActive,
    sendLeafMessage,
    acceptTopicSwitch,
    dismissTopicSwitch,
    dismissClosurePrompt,
    markExplored,

    explorationPending,
    explorationReadyData,
    clearExplorationReady,
  } = useExploration({
    initialSessionId,
    autoCreateSession: !initialSessionId,
  });

  // Close feedback: announce where the user landed and focus a "next topic /
  // chat input" skip-link. Wraps open/close/mark-explored.
  const { closeInfo, handleOpenLeaf, handleClose, handleMarkExplored } =
    useLeafCloseFlow({
      trees,
      activeLeaf,
      activeLeafNode,
      openLeaf,
      closeLeaf,
      markExplored,
    });

  // Navigate to canonical session URL once the session is created.
  useEffect(() => {
    if (sessionId && !initialSessionId && !hasNavigated.current) {
      hasNavigated.current = true;
      router.replace(`/${contextId}/explore/${sessionId}`);
    }
  }, [sessionId, initialSessionId, contextId, router]);

  // Clear the one-shot exploration_ready signal once observed; the tree
  // card has already rendered by the time we get here.
  useEffect(() => {
    if (explorationReadyData) {
      clearExplorationReady();
    }
  }, [explorationReadyData, clearExplorationReady]);

  // The most-recently-received tree is the one we preview while
  // `explorationPending` is true (between EXPLORATION_TREE_RECEIVED and
  // EXPLORATION_READY).
  const pendingTree = useMemo(
    () => (explorationPending ? (trees[trees.length - 1] ?? null) : null),
    [explorationPending, trees],
  );

  // Deep link: ?leaf=<id> opens the matching leaf sidebar once the leaf
  // can be resolved to a tree. Runs once per mount so closing the sheet
  // doesn't re-open it.
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
    handleOpenLeaf(deepLinkExplorationId, deepLinkLeaf);
  }, [deepLinkLeaf, deepLinkExplorationId, handleOpenLeaf]);

  // First browser-back press closes the leaf sheet instead of leaving
  // the page — particularly meaningful on mobile.
  const isLeafOpen = !!activeLeaf;
  useLeafBackInterception({ isOpen: isLeafOpen, onBack: handleClose });

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-4">
        <p className="text-destructive">{error.message}</p>
      </div>
    );
  }

  if (!isConnected && mode === 'idle') {
    return <ExplorationLoading message="Verbindung wird hergestellt..." />;
  }

  return (
    <div
      id="main-content"
      tabIndex={-1}
      className="flex flex-1 flex-col overflow-hidden focus:outline-none"
    >
      <LeafCloseAnnouncer info={closeInfo} />

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
        onSendMessageAction={sendChatMessage}
        onSubmitChoiceAction={submitChoice}
        onDirectionChoiceAction={submitDirectionChoice}
        onOpenLeafAction={handleOpenLeaf}
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
        showClosurePrompt={leafClosureActive}
        onSendMessage={sendLeafMessage}
        onAcceptSwitch={
          leafTopicSwitchSuggestion
            ? () => acceptTopicSwitch(leafTopicSwitchSuggestion.targetNodeId)
            : undefined
        }
        onDismissSwitch={dismissTopicSwitch}
        onMarkExplored={activeLeaf ? handleMarkExplored : undefined}
        onContinueExploring={dismissClosurePrompt}
        onClose={handleClose}
      />
    </div>
  );
}
