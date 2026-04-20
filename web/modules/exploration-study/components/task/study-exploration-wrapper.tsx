'use client';

import {
  ExplorationChatView,
  ExplorationFullView,
  ExplorationLoading,
} from '@/modules/guided-exploration/components';
import { KnowledgeBaseDebug } from '@/modules/guided-exploration/components/debug/knowledge-base-debug';
import {
  EXPLORATION_PANEL_ID,
  ExplorationTabBar,
} from '@/modules/guided-exploration/components/layout/exploration-tab-bar';
import { ErrorBanner } from '@/modules/guided-exploration/components/shared';
import { useExploration } from '@/modules/guided-exploration/hooks';
import {
  sessionActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import { StudyTopicSidebar } from './study-topic-sidebar';

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
 * Study task exploration view.
 *
 * URL-synced via query params on `/exploration-study/[sessionId]/task`:
 *   - `?exploration=<id>` — which exploration tab is active
 *   - `?path=<a,b,c>` — current path within that exploration
 *
 * The URL is the source of truth; effects hydrate the Zustand store from
 * the URL, and navigation handlers write to the URL via `router.replace`
 * (no history pollution during a study session).
 */
export function StudyExplorationWrapper({
  chatId,
  onReady,
  studyTopicLabel,
}: StudyExplorationWrapperProps) {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const studySessionId = params.sessionId as string;

  const hasNotifiedReady = useRef(false);
  const loadedExplorations = useRef<Set<string>>(new Set());
  const lastNavigatedPath = useRef<string | null>(null);
  const dispatch = useExplorationStore((s) => s.dispatch);

  const urlExploration = searchParams.get('exploration');
  const urlPathStr = searchParams.get('path');
  const urlPath = useMemo(
    () => (urlPathStr ? urlPathStr.split(',').filter(Boolean) : []),
    [urlPathStr],
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
    isThinking,
    thinkingMessage,
    sendMessage,
    sendChatMessage,
    loadExploration,
    submitChoice,
    submitDirectionChoice,
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
    activeTabId,
    explorationTabs,
  } = useExploration({
    initialSessionId: chatId,
    autoCreateSession: false,
  });

  const buildStudyUrl = useCallback(
    (explorationId: string | null, path: string[]) => {
      const base = `/exploration-study/${studySessionId}/task`;
      if (!explorationId) return base;
      const qs = new URLSearchParams();
      qs.set('exploration', explorationId);
      if (path.length > 0) qs.set('path', path.join(','));
      return `${base}?${qs.toString()}`;
    },
    [studySessionId],
  );

  useEffect(() => {
    if (isConnected && !hasNotifiedReady.current) {
      hasNotifiedReady.current = true;
      onReady?.();
    }
  }, [isConnected, onReady]);

  // URL -> store: load exploration when URL points at one we haven't loaded.
  useEffect(() => {
    if (!urlExploration || !isConnected) return;
    if (loadedExplorations.current.has(urlExploration)) return;
    loadedExplorations.current.add(urlExploration);
    loadExploration(urlExploration).catch(() => {
      loadedExplorations.current.delete(urlExploration);
    });
  }, [urlExploration, isConnected, loadExploration]);

  // URL -> store: keep activeTabId in sync with the `?exploration=` param.
  useEffect(() => {
    const target: 'chat' | string = urlExploration ?? 'chat';
    if (activeTabId !== target) {
      dispatch(sessionActions.tabSwitched(target, currentPath));
    }
    // currentPath intentionally omitted — tabSwitched only needs it as the
    // "previousPath" breadcrumb, and re-firing this effect on every nav
    // would cause infinite loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlExploration, activeTabId, dispatch]);

  // URL -> store: navigate the tree when `?path=` differs from currentPath.
  useEffect(() => {
    if (!urlExploration || !isConnected || !tree) return;
    const urlJoined = urlPath.join(',');
    if (lastNavigatedPath.current === urlJoined) return;
    if (urlJoined !== currentPath.join(',')) {
      lastNavigatedPath.current = urlJoined;
      navigateOptimistically(urlPath);
    }
  }, [
    urlExploration,
    isConnected,
    tree,
    urlPath,
    currentPath,
    navigateOptimistically,
  ]);

  // `exploration_ready` arrives when the backend finishes building a new
  // tree in response to a chat message. Add a tab for it and switch via URL.
  useEffect(() => {
    if (!explorationReadyData) return;
    const { explorationId } = explorationReadyData;
    clearExplorationReady();

    if (!explorationTabs[explorationId]) {
      const startMsg = sessionMessages.find(
        (m) =>
          m.type === 'exploration_start' && m.explorationId === explorationId,
      );
      const query = startMsg?.explorationQuery || 'Erkundung';
      const label = query.length > 30 ? `${query.slice(0, 27)}...` : query;
      const tabCount = Object.keys(explorationTabs).length;
      dispatch(
        sessionActions.explorationTabAdded(explorationId, label, tabCount % 6),
      );
    }

    router.replace(buildStudyUrl(explorationId, []));
  }, [
    explorationReadyData,
    clearExplorationReady,
    explorationTabs,
    sessionMessages,
    dispatch,
    router,
    buildStudyUrl,
  ]);

  const handleNavigateToRoot = useCallback(() => {
    if (urlExploration) {
      router.replace(buildStudyUrl(urlExploration, []));
    }
  }, [router, urlExploration, buildStudyUrl]);

  const handleNavigateToTopic = useCallback(
    (topicId: string) => {
      if (urlExploration) {
        router.replace(buildStudyUrl(urlExploration, [topicId]));
      }
    },
    [router, urlExploration, buildStudyUrl],
  );

  const handleNavigateToSubtopic = useCallback(
    (nodeId: string) => {
      if (urlExploration) {
        router.replace(buildStudyUrl(urlExploration, [...currentPath, nodeId]));
      }
    },
    [router, urlExploration, currentPath, buildStudyUrl],
  );

  const handleBack = useCallback(() => {
    if (urlExploration && currentPath.length > 0) {
      router.replace(buildStudyUrl(urlExploration, currentPath.slice(0, -1)));
    }
  }, [router, urlExploration, currentPath, buildStudyUrl]);

  const handleTabSwitch = useCallback(
    (tabId: 'chat' | string) => {
      dispatch(sessionActions.tabSwitched(tabId, currentPath));
      if (tabId === 'chat') {
        router.replace(buildStudyUrl(null, []));
      } else {
        const targetTab = explorationTabs[tabId];
        const restoredPath = targetTab?.lastPath ?? [];
        router.replace(buildStudyUrl(tabId, restoredPath));
      }
    },
    [dispatch, currentPath, router, buildStudyUrl, explorationTabs],
  );

  const handleTabClose = useCallback(
    (explorationId: string) => {
      dispatch(sessionActions.explorationTabRemoved(explorationId));
      if (activeTabId === explorationId) {
        router.replace(buildStudyUrl(null, []));
      }
    },
    [dispatch, activeTabId, router, buildStudyUrl],
  );

  const handleEnterExploration = useCallback(
    (explorationId: string) => {
      if (!explorationTabs[explorationId]) {
        const startMsg = sessionMessages.find(
          (m) =>
            m.type === 'exploration_start' && m.explorationId === explorationId,
        );
        const query = startMsg?.explorationQuery || 'Erkundung';
        const label = query.length > 30 ? `${query.slice(0, 27)}...` : query;
        const tabCount = Object.keys(explorationTabs).length;
        dispatch(
          sessionActions.explorationTabAdded(
            explorationId,
            label,
            tabCount % 6,
          ),
        );
      }
      handleTabSwitch(explorationId);
    },
    [explorationTabs, sessionMessages, dispatch, handleTabSwitch],
  );

  const handleDismissError = useCallback(() => {
    dispatch(uiActions.errorCleared());
  }, [dispatch]);

  if (!isConnected && mode === 'idle') {
    return <ExplorationLoading message="Verbindung wird hergestellt..." />;
  }

  const isExplorationActive = !!urlExploration && !!sessionId;
  const isExplorationLoaded = isExplorationActive && !!tree;
  const isExplorationLoading = isExplorationActive && !tree;
  const studySidebar = tree ? (
    <StudyTopicSidebar tree={tree} summaries={summaries} />
  ) : null;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {error && (
        <ErrorBanner message={error.message} onDismiss={handleDismissError} />
      )}

      <ExplorationTabBar
        activeTabId={activeTabId}
        explorationTabs={explorationTabs}
        isInExploration={isExplorationActive}
        onTabSwitch={handleTabSwitch}
        onTabClose={handleTabClose}
      />

      <div
        id={EXPLORATION_PANEL_ID}
        role="tabpanel"
        aria-labelledby={`exploration-tab-${activeTabId}`}
        className="flex flex-1 flex-col overflow-hidden focus:outline-none"
      >
        {isExplorationLoading && (
          <ExplorationLoading message="Erkundung wird geladen..." />
        )}

        {isExplorationLoaded ? (
          <>
            <ExplorationFullView
              tree={tree}
              view={view}
              currentPath={currentPath}
              breadcrumb={breadcrumb}
              activeConversation={activeConversation}
              summaries={summaries}
              isThinking={isThinking}
              thinkingMessage={thinkingMessage}
              isStreaming={isStreaming}
              streamBuffer={streamBuffer}
              streamingTargetType={streamingTarget?.type}
              onNavigate={handleNavigateToTopic}
              onGoToRoot={handleNavigateToRoot}
              onSubtopicSelect={handleNavigateToSubtopic}
              onBack={handleBack}
              onSendMessage={(msg) =>
                sendMessage(msg, activeConversation?.leafId)
              }
              onMarkExplored={markExplored}
              suggestedQuestions={suggestedQuestions}
              sidebar={studySidebar}
              hideLeafDoneButton
              onExitToChat={() => handleTabSwitch('chat')}
            />
            {sessionId && urlExploration && (
              <KnowledgeBaseDebug
                sessionId={sessionId}
                explorationId={urlExploration}
                tree={tree}
              />
            )}
          </>
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
            studyTopicLabel={studyTopicLabel}
            minDirections={3}
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
