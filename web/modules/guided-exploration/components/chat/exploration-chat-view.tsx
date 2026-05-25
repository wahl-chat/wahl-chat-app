'use client';

import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type {
  ChoicePromptEvent,
  ExplorationTree,
  SessionMessage,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { useEffect, useRef, useState } from 'react';

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
  const scrollContainerRef = useRef<HTMLElement>(null);
  const lastUserMessageRef = useRef<HTMLDivElement>(null);
  const lastBotMessageRef = useRef<HTMLDivElement>(null);
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

  // On send, scroll the user's message to the top of the scroll container
  // (not the page) and move focus onto it — the single managed focus move.
  // Without the focus move the composer disables on submit and the browser
  // drops focus to <body> (the "jumps to top-left" bug). Bot responses don't
  // grab focus: they're announced via the status region and the user navigates
  // to them by heading at their own pace.
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

          // Calculate the wrapper's position relative to the scroll container
          // (the sr-only heading is position:absolute, so its own offsetTop is
          // meaningless — the wrapper is the scroll anchor).
          const elementTop = element.offsetTop - container.offsetTop;
          container.scrollTo({
            top: elementTop - 24, // 24px padding from top
            behavior: 'smooth',
          });
          // Focus the message's heading (announces "Du: …" once), not the
          // wrapper. preventScroll: our scrollTo already positioned it.
          element.querySelector('h2')?.focus({ preventScroll: true });
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

  // The most recent non-user message. The assistant turn only lands in
  // `messages` once it's complete (streaming lives in `streamBuffer`), so a new
  // id here means "the answer just settled".
  let lastBotMessage: SessionMessage | null = null;
  let lastBotMessageIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].type !== 'user') {
      lastBotMessage = messages[i];
      lastBotMessageIndex = i;
      break;
    }
  }

  // Seed the "already announced" id from whatever is present on the first
  // render so a resumed/hydrated transcript doesn't fire a cue on load. A
  // fresh session seeds `null`, so its very first answer still announces.
  const seenBotIdRef = useRef<string | null>(null);
  const didSeedRef = useRef(false);
  if (!didSeedRef.current) {
    didSeedRef.current = true;
    seenBotIdRef.current = lastBotMessage?.id ?? null;
  }

  // Arrival handling. We announce only for the direction-selection prompt —
  // there's no answer to read there, so a spoken cue is the signal. For
  // assistant answers we stay silent in the live region and let the focus move
  // (below) onto the heading announce arrival ("KI: …"); a competing
  // "Antwort fertig." cue would interrupt a continuous read before it reaches
  // the party cards and falsely signal completion.
  const [finishedCue, setFinishedCue] = useState('');
  useEffect(() => {
    if (!lastBotMessage || seenBotIdRef.current === lastBotMessage.id) return;
    seenBotIdRef.current = lastBotMessage.id;

    const cue =
      lastBotMessage.type === 'topic_directions'
        ? 'Bitte wähle Aspekte aus.'
        : '';
    setFinishedCue(cue);

    // Move focus onto the settled message so the cursor lands at the top of the
    // new reply (its <h2> announces "KI: …"). Mirrors the scroll+focus the user
    // message gets on send.
    requestAnimationFrame(() => {
      const container = scrollContainerRef.current;
      const element = lastBotMessageRef.current;
      if (!container || !element) return;
      const elementTop = element.offsetTop - container.offsetTop;
      container.scrollTo({ top: elementTop - 24, behavior: 'smooth' });
      // Focus the message's heading (data-answer-start marks the latest bot
      // one) so the cursor lands on "KI: …" / "Aspekt-Auswahl" — a heading,
      // announced as "Überschrift" in every browser, never "group".
      const target =
        element.querySelector<HTMLElement>('[data-answer-start]') ??
        element.querySelector<HTMLElement>('h2');
      target?.focus({ preventScroll: true });
    });

    if (!cue) return;
    const clear = setTimeout(() => setFinishedCue(''), 4500);
    return () => clearTimeout(clear);
  }, [lastBotMessage]);

  // The choice prompt ("Wie möchtest du das Thema angehen?") isn't a message,
  // so it never gets the settle focus above. Without this it lands the user
  // nowhere and its only announcement (the status region) is easily missed.
  // Move focus onto its heading when it appears so arrival is unmistakable and
  // the options are one tab away.
  const choicePromptRef = useRef<HTMLDivElement>(null);
  const seenChoiceIdRef = useRef<string | null>(null);
  useEffect(() => {
    const id = pendingChoice?.queryId ?? null;
    if (!id) {
      seenChoiceIdRef.current = null;
      return;
    }
    if (seenChoiceIdRef.current === id) return;
    seenChoiceIdRef.current = id;

    requestAnimationFrame(() => {
      const container = scrollContainerRef.current;
      const wrapper = choicePromptRef.current;
      if (!container || !wrapper) return;
      const elementTop = wrapper.offsetTop - container.offsetTop;
      container.scrollTo({ top: elementTop - 24, behavior: 'smooth' });
      wrapper.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
    });
  }, [pendingChoice]);

  // One narration region drives all transient speech: process state while the
  // answer is generating, then the brief arrival cue once it settles.
  const statusText = (() => {
    if (isStreaming) return 'KI-Antwort wird geschrieben.';
    if (isThinking) {
      return thinkingMessage ?? 'Nachricht wird verarbeitet...';
    }
    if (pendingChoice) {
      return 'Du kannst jetzt oben wählen: „Schnelle Antwort" für eine kompakte Übersicht oder „Thema vertiefen", um Aspekte im Detail zu vergleichen.';
    }
    return finishedCue;
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
      {/* Conversation landmark: the scrollable transcript. A labelled region
          is how screen-reader users jump *to* the conversation; the per-message
          <h2> headings inside are how they jump *through* it. No rendered
          heading here — that would just be one more thing to skip before the
          first message. */}
      <section
        ref={scrollContainerRef}
        aria-label="Gesprächsverlauf"
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
                lastBotMessageIndex={lastBotMessageIndex}
                lastBotMessageRef={lastBotMessageRef}
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
                <div ref={choicePromptRef}>
                  <ChoicePromptCard
                    choice={pendingChoice}
                    onSubmit={(choice) =>
                      onSubmitChoiceAction(pendingChoice.queryId, choice)
                    }
                    isLoading={isThinking}
                  />
                </div>
              )}
            </div>
          )}
          <div style={{ height: '3rem' }} />
        </div>
      </section>

      {/* Composer landmark: a sibling of the conversation so users can flip
          between "Gesprächsverlauf" and the input with one landmark keystroke. */}
      <section
        aria-label="Nachricht an die KI"
        className="sticky bottom-0 w-full border-t bg-background px-4 py-3"
      >
        <div className="mx-auto w-full max-w-xl">
          <ConversationInput
            inputId="chat-input"
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
      </section>
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
