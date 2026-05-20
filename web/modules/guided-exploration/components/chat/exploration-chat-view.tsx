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
  /** Minimum number of directions the user must select (used in study mode). */
  minDirections?: number;
  onSendMessageAction: (message: string) => void;
  onSubmitChoiceAction: (
    queryId: string,
    choice: 'summary' | 'explore',
  ) => void;
  onDirectionChoiceAction?: (
    queryId: string,
    directions: Array<{ id: string; name: string }>,
  ) => void;
  /** Open a leaf in the sub-chat sidebar. */
  onOpenLeafAction?: (explorationId: string, leafId: string) => void;
  /** When set, the matching tree card auto-expands the ancestor chain. */
  deepLinkExplorationId?: string | null;
  /** Leaf id from a `?leaf=<id>` deep link, forwarded to the matching card. */
  deepLinkLeafId?: string | null;
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
  minDirections,
  onSendMessageAction,
  onSubmitChoiceAction,
  onDirectionChoiceAction,
  onOpenLeafAction,
  deepLinkExplorationId,
  deepLinkLeafId,
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
  // (covers the gap between stream_end and the final chat_message arriving).
  // Only `quick_summary` is a chat-tab stream — `followup`/`initial_content`/
  // `analysis` are leaf-scoped and must not bleed into the chat view.
  const isStreamableType = streamingTargetType === 'quick_summary';
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

  const statusText = (() => {
    if (isStreaming) return 'KI-Antwort wird geschrieben.';
    if (isThinking) {
      return thinkingMessage ?? 'Nachricht wird verarbeitet...';
    }
    if (pendingChoice) {
      return 'Du kannst jetzt oben wählen: „Schnelle Antwort" für eine kompakte Übersicht oder „Thema vertiefen", um Aspekte im Detail zu vergleichen.';
    }
    return '';
  })();

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Persistent status announcer for thinking/streaming state and
          pending choice prompts. */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {statusText}
      </div>
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
        <div className="mx-auto w-full max-w-xl py-8">
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
                onOpenLeafAction={onOpenLeafAction}
                onDirectionChoiceAction={onDirectionChoiceAction}
                isLoading={isThinking}
                lastUserMessageIndex={lastUserMessageIndex}
                lastUserMessageRef={lastUserMessageRef}
                minDirections={minDirections}
                deepLinkExplorationId={deepLinkExplorationId}
                deepLinkLeafId={deepLinkLeafId}
              />

              {/*
                Streaming content with citation mapping. Not a live region
                — per-token aria-live updates flood the screen reader with
                partial words. The outer "statusText" status
                announces "KI-Antwort wird geschrieben" once at start, and
                the final message is read when it lands in SessionMessageList.
              */}
              {shouldShowStreamBuffer && (
                <div aria-hidden="true">
                  <ChatStreamingBuffer
                    content={streamBuffer}
                    isStreaming={isStreaming}
                  />
                </div>
              )}

              {/* Tree preview while exploration is pending */}
              {showTreePreview && (
                <TopicTreePreview
                  tree={tree}
                  thinkingMessage={thinkingMessage}
                />
              )}

              {/* Thinking indicator (only when no tree preview).
                  announce=false because the outer persistent status region
                  (above) already owns the SR announcement for thinking. */}
              {isThinking && !isStreaming && !showTreePreview && (
                <ThinkingIndicator
                  message={thinkingMessage ?? undefined}
                  announce={false}
                />
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
        </div>
      </div>

      {/* Input - sticky at bottom */}
      <div className="sticky bottom-0 w-full border-t bg-background px-4 py-3">
        <div className="mx-auto w-full max-w-xl">
          <ConversationInput
            onSubmit={onSendMessageAction}
            disabled={isThinking || !!pendingChoice || hasActiveDirections}
            disabledReason={
              pendingChoice
                ? 'Wähle zuerst oben eine Option, um fortzufahren.'
                : hasActiveDirections
                  ? 'Wähle zuerst oben die Aspekte aus, die dich interessieren.'
                  : isThinking
                    ? 'Die Antwort wird gerade generiert. Bitte warte einen Moment.'
                    : undefined
            }
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
