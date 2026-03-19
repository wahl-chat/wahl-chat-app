'use client';

import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type {
  ChoicePromptEvent,
  ExplorationTree,
  SessionMessage,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { useEffect, useRef } from 'react';

import { ConversationInput } from '@/modules/guided-exploration/components/conversation/conversation-input';
import { ThinkingIndicator } from '@/modules/guided-exploration/components/conversation/thinking-indicator';
import { ChoicePromptCard } from './choice-prompt-card';
import { ExplorationEmptyView } from './exploration-empty-view';
import { SessionMessageList } from './session-message-list';
import { TopicTreePreview } from './topic-tree-preview';

interface ExplorationChatViewProps {
  messages: SessionMessage[];
  pendingChoice: ChoicePromptEvent | null;
  isThinking: boolean;
  thinkingMessage: string | null;
  streamBuffer: string;
  isStreaming: boolean;
  /** The type of content being streamed */
  streamingTargetType?: StreamTargetType | null;
  /** Tree preview (shown when exploration is pending) */
  tree: ExplorationTree | null;
  /** Whether exploration is pending (tree received, waiting for ready) */
  explorationPending: boolean;
  /** Suggested follow-up questions shown above the input */
  suggestedQuestions?: string[];
  onSendMessageAction: (message: string) => void;
  onSubmitChoiceAction: (
    queryId: string,
    choice: 'summary' | 'explore',
  ) => void;
  onEnterExplorationAction: (explorationId: string) => void;
}

export function ExplorationChatView({
  messages,
  pendingChoice,
  isThinking,
  thinkingMessage,
  streamBuffer,
  isStreaming,
  streamingTargetType,
  tree,
  explorationPending,
  suggestedQuestions = [],
  onSendMessageAction,
  onSubmitChoiceAction,
  onEnterExplorationAction,
}: ExplorationChatViewProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const hasMessages = messages.length > 0;
  const showTreePreview = explorationPending && tree;

  // Only show stream buffer for markdown-based content types
  const shouldShowStreamBuffer =
    isStreaming &&
    streamBuffer &&
    (streamingTargetType === 'quick_summary' ||
      streamingTargetType === 'followup');

  // Debug streaming state
  console.log('[ExplorationChatView] streaming state:', {
    isStreaming,
    streamBufferLength: streamBuffer?.length ?? 0,
    streamingTargetType,
    shouldShowStreamBuffer,
  });

  // Auto-scroll to bottom when thinking starts or new messages arrive
  useEffect(() => {
    if (isThinking || isStreaming || messages.length > 0) {
      scrollContainerRef.current?.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [isThinking, isStreaming, messages.length]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Main content area - with gradient mask */}
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
        <main className="mx-auto w-full max-w-xl py-8">
          {!hasMessages ? (
            <ExplorationEmptyView onSuggestionClick={onSendMessageAction} />
          ) : (
            <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6">
              <SessionMessageList
                messages={messages}
                onEnterExplorationAction={onEnterExplorationAction}
                isLoading={isThinking}
              />

              {/* Streaming content - only for markdown-based streams */}
              {shouldShowStreamBuffer && (
                <PartyMarkedMarkdown
                  onReferenceClick={() => {}}
                  isStreaming={isStreaming}
                >
                  {streamBuffer}
                </PartyMarkedMarkdown>
              )}

              {/* Tree preview while exploration is pending */}
              {showTreePreview && (
                <TopicTreePreview
                  tree={tree}
                  thinkingMessage={thinkingMessage}
                />
              )}

              {/* Thinking indicator (only when no tree preview) */}
              {isThinking && !isStreaming && !showTreePreview && (
                <ThinkingIndicator message={thinkingMessage ?? undefined} />
              )}

              {/* Choice prompt */}
              {pendingChoice && (
                <ChoicePromptCard
                  choice={pendingChoice}
                  onSubmit={(choice) =>
                    onSubmitChoiceAction(pendingChoice.queryId, choice)
                  }
                  isLoading={isThinking}
                />
              )}
            </div>
          )}
          <div style={{ height: '3rem' }} />
        </main>
      </div>

      {/* Input - sticky at bottom */}
      <div className="sticky bottom-0 w-full border-t bg-background px-4 py-3">
        <div className="mx-auto w-full max-w-xl">
          <ConversationInput
            onSubmit={onSendMessageAction}
            disabled={isThinking || !!pendingChoice}
            placeholder="Stelle eine Frage..."
            suggestedQuestions={suggestedQuestions}
          />
        </div>
      </div>
    </div>
  );
}
