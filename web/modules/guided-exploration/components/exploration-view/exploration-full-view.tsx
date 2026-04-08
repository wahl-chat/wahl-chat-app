'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ConversationInput } from '@/modules/guided-exploration/components/conversation';
import { ExplorationBreadcrumb } from '@/modules/guided-exploration/components/navigation/breadcrumb';
import type {
  BreadcrumbItem,
  Conversation,
  ExplorationTree,
  LeafSummary,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { findNode } from '@/modules/guided-exploration/utils/tree-helpers';
import { Check } from 'lucide-react';
import { useEffect, useRef } from 'react';

import { BranchContent } from './branch-content';
import { ExplorationContextBanner } from './exploration-context-banner';
import { ExplorationSummaryPanel } from './exploration-summary-panel';
import { LeafContent } from './leaf-content';
import { MobileSummarySheet } from './mobile-summary-sheet';
import { RootContent } from './root-content';

export type ExplorationView = 'root' | 'branch' | 'leaf';

interface ExplorationFullViewProps {
  tree: ExplorationTree;
  view: ExplorationView;
  currentPath: string[];
  breadcrumb: BreadcrumbItem[];
  activeConversation: Conversation | null;
  summaries: Record<string, LeafSummary> | null;
  analysisAvailable: boolean;
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
  onRequestAnalysis: () => void;
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
  className?: string;
}

export function ExplorationFullView({
  tree,
  view,
  currentPath,
  breadcrumb,
  activeConversation,
  summaries,
  analysisAvailable,
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
  className,
}: ExplorationFullViewProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messageCount = activeConversation?.messages.length ?? 0;

  const currentNodeId = currentPath[currentPath.length - 1] ?? null;
  const currentBranchNode = currentNodeId
    ? findNode(tree, currentNodeId)
    : undefined;

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

  return (
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
            />
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
                <Button onClick={handleDone} variant="outline" size="sm">
                  <Check className="mr-1.5 size-4" />
                  Thema abschließen
                </Button>
              </div>
              <ConversationInput
                onSubmit={onSendMessage}
                disabled={isThinking}
                placeholder="Stelle eine Frage zu diesem Thema..."
                suggestedQuestions={suggestedQuestions}
                isLoadingQuestions={
                  (isThinking || isStreaming) && suggestedQuestions.length === 0
                }
              />
            </div>
          </footer>
        )}
      </main>

      {/* Summary Panel - Desktop only, wider on large screens */}
      <aside className="hidden w-72 shrink-0 border-l bg-muted/30 md:block lg:w-80 xl:w-96">
        <ExplorationSummaryPanel
          tree={tree}
          currentPath={currentPath}
          summaries={summaries}
          onNavigate={handleSummaryPanelNavigate}
          className="h-full"
        />
      </aside>
    </div>
  );
}
