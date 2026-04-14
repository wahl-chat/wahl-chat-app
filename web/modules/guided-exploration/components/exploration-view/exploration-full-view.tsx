'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ConversationInput } from '@/modules/guided-exploration/components/conversation';
import { ExplorationBreadcrumb } from '@/modules/guided-exploration/components/navigation/breadcrumb';
import type {
  BreadcrumbItem,
  Conversation,
  ExplorationNode,
  ExplorationTree,
  LeafSummary,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { findNode } from '@/modules/guided-exploration/utils/tree-helpers';
import { Check } from 'lucide-react';
import {
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from 'react';

import { BranchContent } from './branch-content';
import { ExplorationContextBanner } from './exploration-context-banner';
import { ExplorationSummaryPanel } from './exploration-summary-panel';
import { LeafContent } from './leaf-content';
import { MobileSummarySheet } from './mobile-summary-sheet';
import { RootContent } from './root-content';

export type ExplorationView = 'root' | 'branch' | 'leaf';

/**
 * Context exposing the currently-active leaf and the "close current leaf"
 * action to any descendant of `ExplorationFullView` — in particular the
 * custom `sidebar` prop, which needs to host the "Thema abschließen"
 * button in study mode without prop-drilling.
 */
interface LeafActionsContextValue {
  activeLeafNode: ExplorationNode | null;
  closeCurrentLeaf: () => void;
}

const LeafActionsContext = createContext<LeafActionsContextValue | null>(null);

export function useLeafActions(): LeafActionsContextValue {
  const ctx = useContext(LeafActionsContext);
  if (!ctx) {
    throw new Error(
      'useLeafActions must be used inside <ExplorationFullView>.',
    );
  }
  return ctx;
}

interface ExplorationFullViewProps {
  tree: ExplorationTree;
  view: ExplorationView;
  currentPath: string[];
  breadcrumb: BreadcrumbItem[];
  activeConversation: Conversation | null;
  summaries: Record<string, LeafSummary> | null;
  analysisAvailable?: boolean;
  isThinking: boolean;
  thinkingMessage?: string | null;
  isStreaming?: boolean;
  streamBuffer?: string;
  streamingTargetType?: StreamTargetType | null;
  onNavigate: (topicId: string) => void;
  onGoToRoot: () => void;
  onSubtopicSelect: (nodeId: string) => void;
  onBack: () => void;
  onSendMessage: (message: string) => void;
  onRequestAnalysis?: () => void;
  onMarkExplored: (leafId: string) => void;
  /** Suggested follow-up questions shown above the input */
  suggestedQuestions?: string[];
  /** Topic switch suggestion from routing agent */
  topicSwitchSuggestion?: {
    targetNodeId: string;
    targetNodeName: string;
    message: string;
  } | null;
  onAcceptSwitch?: (targetNodeId: string) => void;
  onDismissSwitch?: () => void;
  /**
   * Override the right sidebar content. When provided, this replaces the
   * default `ExplorationSummaryPanel` in both the desktop aside and the
   * mobile sheet. Sidebar components can consume `useLeafActions()` to
   * trigger the "close current leaf" action.
   */
  sidebar?: ReactNode;
  /**
   * When true, the per-leaf "Thema abschließen" button is not rendered in
   * the leaf footer. Use this when the button is relocated elsewhere (e.g.
   * into the sidebar in study mode).
   */
  hideLeafDoneButton?: boolean;
  className?: string;
}

export function ExplorationFullView({
  tree,
  view,
  currentPath,
  breadcrumb,
  activeConversation,
  summaries,
  analysisAvailable = false,
  isThinking,
  thinkingMessage,
  isStreaming,
  streamBuffer,
  streamingTargetType,
  onNavigate,
  onGoToRoot,
  onSubtopicSelect,
  onBack,
  onSendMessage,
  onRequestAnalysis,
  onMarkExplored,
  suggestedQuestions = [],
  topicSwitchSuggestion,
  onAcceptSwitch,
  onDismissSwitch,
  sidebar,
  hideLeafDoneButton = false,
  className,
}: ExplorationFullViewProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messageCount = activeConversation?.messages.length ?? 0;

  const currentNodeId = currentPath[currentPath.length - 1] ?? null;
  const currentBranchNode = currentNodeId
    ? findNode(tree, currentNodeId)
    : undefined;

  const activeLeafNode = useMemo<ExplorationNode | null>(() => {
    const leafId = activeConversation?.leafId;
    if (!leafId) return null;
    return findNode(tree, leafId) ?? null;
  }, [tree, activeConversation?.leafId]);

  // Auto-scroll to bottom when thinking starts or new messages arrive
  useEffect(() => {
    if (view === 'leaf' && (isThinking || isStreaming)) {
      scrollContainerRef.current?.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [view, isThinking, isStreaming, messageCount]);

  const handleBreadcrumbNavigate = (
    level: 'root' | 'topic' | 'subtopic',
    id?: string,
  ) => {
    if (level === 'root') {
      onGoToRoot();
    } else if (id) {
      onNavigate(id);
    }
  };

  const handleSummaryPanelNavigate = (nodeId: string) => {
    onNavigate(nodeId);
  };

  /**
   * Handle "Done" button click in leaf view.
   * Marks the leaf as explored, navigates back to branch view, and focuses the next unexplored subtopic.
   */
  const handleDone = () => {
    // Mark the current leaf as explored
    if (activeConversation?.leafId) {
      onMarkExplored(activeConversation.leafId);
    }

    onBack();
    // After navigation, focus next unexplored subtopic
    requestAnimationFrame(() => {
      const nextUnexplored = document.querySelector(
        '[data-subtopic-id][data-status="pending"]',
      ) as HTMLButtonElement | null;
      nextUnexplored?.focus();
    });
  };

  const leafActions = useMemo<LeafActionsContextValue>(
    () => ({
      activeLeafNode,
      closeCurrentLeaf: handleDone,
    }),
    // handleDone depends on activeConversation + callbacks that are stable per render;
    // recomputing when activeLeafNode changes is sufficient.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeLeafNode],
  );

  const defaultSidebarNode = (
    <ExplorationSummaryPanel
      tree={tree}
      currentPath={currentPath}
      summaries={summaries}
      onNavigate={handleSummaryPanelNavigate}
      className="h-full"
    />
  );

  const sidebarNode = sidebar ?? defaultSidebarNode;

  return (
    <LeafActionsContext.Provider value={leafActions}>
      <div className={cn('flex flex-1 overflow-hidden', className)}>
        {/* Main Content */}
        <main className="flex flex-1 flex-col overflow-hidden">
          {/* Breadcrumb header */}
          <header className="shrink-0 border-b bg-background px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ExplorationBreadcrumb
                  items={breadcrumb}
                  onNavigate={handleBreadcrumbNavigate}
                />
              </div>
              {/* Mobile summary sheet trigger */}
              <MobileSummarySheet
                tree={tree}
                currentPath={currentPath}
                summaries={summaries}
                onNavigate={handleSummaryPanelNavigate}
              >
                {sidebar}
              </MobileSummarySheet>
            </div>
          </header>

          {/* Context banner — always visible */}
          <div className="shrink-0 border-b px-4 py-2">
            <ExplorationContextBanner tree={tree} />
          </div>

          {/* Content based on view - with gradient mask */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-auto"
            style={{
              maskImage:
                'linear-gradient(to bottom, transparent, black 2rem, black calc(100% - 2rem), transparent)',
              WebkitMaskImage:
                'linear-gradient(to bottom, transparent, black 2rem, black calc(100% - 2rem), transparent)',
            }}
          >
            <div className="mx-auto w-full max-w-screen-sm p-4 md:p-8">
              {view === 'root' && (
                <RootContent tree={tree} onTopicSelect={onNavigate} />
              )}
              {view === 'branch' && currentBranchNode && (
                <BranchContent
                  node={currentBranchNode}
                  summaries={summaries}
                  onChildSelect={(nodeId) => onSubtopicSelect(nodeId)}
                />
              )}
              {view === 'leaf' && (
                <LeafContent
                  conversation={activeConversation}
                  isThinking={isThinking}
                  thinkingMessage={thinkingMessage}
                  isStreaming={isStreaming}
                  streamBuffer={streamBuffer}
                  streamingTargetType={streamingTargetType}
                  topicSwitchSuggestion={topicSwitchSuggestion}
                  onAcceptSwitch={
                    onAcceptSwitch && topicSwitchSuggestion
                      ? () => onAcceptSwitch(topicSwitchSuggestion.targetNodeId)
                      : undefined
                  }
                  onDismissSwitch={onDismissSwitch}
                />
              )}
            </div>
          </div>

          {/* Input and Done button for leaf view */}
          {view === 'leaf' && (
            <footer className="shrink-0 border-t bg-background">
              <div className="mx-auto flex w-full max-w-2xl flex-col gap-3 px-4 py-3">
                {(!hideLeafDoneButton ||
                  (analysisAvailable && onRequestAnalysis)) && (
                  <div className="flex w-full items-center justify-between">
                    <div>
                      {/* Analysis button */}
                      {analysisAvailable && onRequestAnalysis && (
                        <div>
                          <Button variant="outline" onClick={onRequestAnalysis}>
                            Analyse anfordern
                          </Button>
                        </div>
                      )}
                    </div>
                    {!hideLeafDoneButton && (
                      <Button onClick={handleDone} variant="outline" size="sm">
                        <Check className="mr-1.5 size-4" />
                        Thema abschließen
                      </Button>
                    )}
                  </div>
                )}
                <ConversationInput
                  onSubmit={onSendMessage}
                  disabled={isThinking}
                  placeholder="Stelle eine Frage zu diesem Thema..."
                  suggestedQuestions={suggestedQuestions}
                  isLoadingQuestions={
                    (isThinking || isStreaming) &&
                    suggestedQuestions.length === 0
                  }
                />
              </div>
            </footer>
          )}
        </main>

        {/* Summary Panel - Desktop only, wider on large screens */}
        <aside className="hidden w-72 shrink-0 border-l bg-muted/30 md:block lg:w-80 xl:w-96">
          {sidebarNode}
        </aside>
      </div>
    </LeafActionsContext.Provider>
  );
}
