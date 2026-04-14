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
import { useStreamingCitationMap } from '@/modules/guided-exploration/utils';
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
  /** When set, restricts the empty-view topic buttons to the assigned study topic. */
  studyTopicLabel?: string;
  onSendMessageAction: (message: string) => void;
  onSubmitChoiceAction: (
    queryId: string,
    choice: 'summary' | 'explore',
  ) => void;
  onDirectionChoiceAction?: (
    queryId: string,
    directions: Array<{ id: string; name: string }>,
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
  studyTopicLabel,
  onSendMessageAction,
  onSubmitChoiceAction,
  onDirectionChoiceAction,
  onEnterExplorationAction,
}: ExplorationChatViewProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const lastUserMessageRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(messages.length);

  const hasMessages = messages.length > 0;
  const showTreePreview = explorationPending && tree;
  const hasActiveDirections =
    messages.length > 0 &&
    messages[messages.length - 1]?.type === 'topic_directions' &&
    !messages[messages.length - 1]?.selectedDirections;

  // Show stream buffer while streaming OR while buffer still has content
  // (covers the gap between stream_end and the final chat_message arriving)
  const isStreamableType =
    streamingTargetType === 'quick_summary' ||
    streamingTargetType === 'followup';
  const shouldShowStreamBuffer =
    !!streamBuffer && (isStreaming ? isStreamableType : true);

  // Scroll the user's message to the top of the scroll container (not the page).
  // Don't auto-scroll for bot responses — let them render below in view.
  useEffect(() => {
    const newCount = messages.length;
    const prevCount = prevMessageCountRef.current;
    prevMessageCountRef.current = newCount;

    if (newCount > prevCount) {
      const lastMessage = messages[newCount - 1];
      if (
        lastMessage?.type === 'user' &&
        lastUserMessageRef.current &&
        scrollContainerRef.current
      ) {
        requestAnimationFrame(() => {
          const container = scrollContainerRef.current;
          const element = lastUserMessageRef.current;
          if (!container || !element) return;

          // Calculate element's position relative to the scroll container
          const elementTop = element.offsetTop - container.offsetTop;
          container.scrollTo({
            top: elementTop - 24, // 24px padding from top
            behavior: 'smooth',
          });
        });
      }
    }
  }, [messages]);

  // Find the index of the last user message for the scroll anchor
  const lastUserMessageIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].type === 'user') return i;
    }
    return -1;
  })();

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Main content area */}
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
            <ExplorationEmptyView
              onSuggestionClick={onSendMessageAction}
              studyTopic={
                studyTopicLabel ? { label: studyTopicLabel } : undefined
              }
            />
          ) : (
            <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6">
              <SessionMessageList
                messages={messages}
                onEnterExplorationAction={onEnterExplorationAction}
                onDirectionChoiceAction={onDirectionChoiceAction}
                isLoading={isThinking}
                lastUserMessageIndex={lastUserMessageIndex}
                lastUserMessageRef={lastUserMessageRef}
              />

              {/* Streaming content with citation mapping */}
              {shouldShowStreamBuffer && (
                <ChatStreamingBuffer
                  content={streamBuffer}
                  isStreaming={isStreaming}
                />
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
            disabled={isThinking || !!pendingChoice || hasActiveDirections}
            placeholder="Stelle eine Frage..."
            suggestedQuestions={suggestedQuestions}
          />
        </div>
      </div>
    </div>
  );
}

function ChatStreamingBuffer({
  content,
  isStreaming,
}: {
  content: string;
  isStreaming: boolean;
}) {
  const { getReferenceName } = useStreamingCitationMap(content);

  return (
    <PartyMarkedMarkdown
      onReferenceClick={() => {}}
      getReferenceName={getReferenceName}
      isStreaming={isStreaming}
    >
      {content}
    </PartyMarkedMarkdown>
  );
}
