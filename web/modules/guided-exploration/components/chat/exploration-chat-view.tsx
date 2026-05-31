'use client';

import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type {
  ChoicePromptEvent,
  ExplorationTree,
  SessionMessage,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { useCallback, useEffect, useRef, useState } from 'react';

import { ConversationInput } from '@/modules/guided-exploration/components/conversation/conversation-input';
import { ThinkingIndicator } from '@/modules/guided-exploration/components/conversation/thinking-indicator';
import { useStreamingCitationMap } from '@/modules/guided-exploration/utils';
import { ChoicePromptCard } from './choice-prompt-card';
import { ExplorationEmptyView } from './exploration-empty-view';
import { SessionMessageList } from './session-message-list';
import { TopicTreePreview } from './topic-tree-preview';

// Polite cues for arrivals. The headings carry the detail; the cue flags that
// something new is here, says what kind, and points at the heading rotor — no
// focus steal. Action gates (choice, aspect selection) name themselves so the
// user knows a decision is waiting, not just a new answer.
const SENT_ANNOUNCEMENT = 'Nachricht gesendet.';
const ANSWER_ANNOUNCEMENT = `Neue Antwort der KI.`;
const DIRECTIONS_ANNOUNCEMENT = `Aspekt-Auswahl verfügbar.`;
const CHOICE_ANNOUNCEMENT = `Auswahl verfügbar: Wie möchtest du das Thema angehen?`;

/** Arrival cue for a settled bot message, by type. */
function botArrivalAnnouncement(type: SessionMessage['type']): string {
  return type === 'topic_directions'
    ? DIRECTIONS_ANNOUNCEMENT
    : ANSWER_ANNOUNCEMENT;
}

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
  const lastBotMessageRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(messages.length);

  const hasMessages = messages.length > 0;
  const showTreePreview = explorationPending && tree;

  // Polite announcement for new arrivals. Bumping the key re-mounts the inner
  // span (the live region itself stays put) so an identical string re-announces.
  const [arrival, setArrival] = useState({ text: '', key: 0 });
  const announce = useCallback((text: string) => {
    setArrival((prev) => ({ text, key: prev.key + 1 }));
  }, []);

  // Show stream buffer while streaming OR while buffer still has content
  // (covers the gap between stream_end and the final chat_message arriving).
  // Only `quick_summary` is a chat-tab stream — `followup`/`initial_content`/
  // `analysis` are leaf-scoped and must not bleed into the chat view.
  const isStreamableType = streamingTargetType === 'quick_summary';
  const shouldShowStreamBuffer =
    !!streamBuffer && (isStreaming ? isStreamableType : true);

  // On send, confirm the message went through (SR users don't see it appear)
  // and scroll it to the top of the scroll container so it's visible. No focus
  // move: the composer stays enabled, so focus stays in the input where the
  // user is, and they read on at their pace.
  useEffect(() => {
    const newCount = messages.length;
    const prevCount = prevMessageCountRef.current;
    prevMessageCountRef.current = newCount;

    if (newCount > prevCount) {
      const lastMessage = messages[newCount - 1];
      if (lastMessage?.type !== 'user') return;

      announce(SENT_ANNOUNCEMENT);

      if (lastUserMessageRef.current && scrollContainerRef.current) {
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
        });
      }
    }
  }, [messages, announce]);

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

  // Arrival handling: announce that a new message settled and scroll it into
  // view, but never move focus. The user jumps to it via the heading rotor when
  // ready — the per-message <h2> carries "KI: …" / "Aspekt-Auswahl".
  useEffect(() => {
    if (!lastBotMessage || seenBotIdRef.current === lastBotMessage.id) return;
    seenBotIdRef.current = lastBotMessage.id;

    const arrivalType = lastBotMessage.type;
    // Defer by a frame: arrivals that follow thinking directly (e.g.
    // `topic_directions`) clear the thinking state in the same commit that
    // produces this arrival, so the process-state region empties in the same
    // tick. Two polite regions mutating together is unreliable for screen
    // readers — acting on the next frame separates the two updates.
    requestAnimationFrame(() => {
      // The choice confirmation is the user's own action landing in the
      // transcript: move focus onto its heading so it's read once ("… ausge-
      // wählt.") and focus isn't dropped to <body> as the choice card unmounts.
      // It carries no "new answer" cue — the real result that follows does.
      if (arrivalType === 'choice_result') {
        lastBotMessageRef.current?.querySelector<HTMLElement>('h2')?.focus();
      } else {
        announce(botArrivalAnnouncement(arrivalType));
      }

      const container = scrollContainerRef.current;
      const element = lastBotMessageRef.current;
      if (!container || !element) return;
      const elementTop = element.offsetTop - container.offsetTop;
      container.scrollTo({ top: elementTop - 24, behavior: 'smooth' });
    });
  }, [lastBotMessage, announce]);

  // The choice prompt ("Wie möchtest du das Thema angehen?") isn't a message,
  // so it isn't covered by the arrival effect above. Announce it and scroll it
  // into view the same way — the user navigates to its heading when ready.
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

    // Defer by a frame: `CHOICE_PROMPTED` clears thinking and sets the choice
    // in one commit, so the process-state region empties in the same tick this
    // would announce in. Announcing next frame avoids two polite regions
    // mutating together, which screen readers drop.
    requestAnimationFrame(() => {
      announce(CHOICE_ANNOUNCEMENT);

      const container = scrollContainerRef.current;
      const wrapper = choicePromptRef.current;
      if (!container || !wrapper) return;
      const elementTop = wrapper.offsetTop - container.offsetTop;
      container.scrollTo({ top: elementTop - 24, behavior: 'smooth' });
    });
  }, [pendingChoice, announce]);

  // When an exploration/study starts, the empty-view topic button vanishes and
  // the browser would otherwise drop focus to <body> — which also flushes any
  // pending polite announcement. Move focus once onto the first message's
  // heading ("Du: …") so the user lands at the top of the new conversation on a
  // named element (VO reads "Du: …, Überschrift", not a generic region), and
  // the later thinking/arrival cues fire in their own ticks, uninterrupted.
  const prevHasMessagesRef = useRef(hasMessages);
  useEffect(() => {
    const wasEmpty = !prevHasMessagesRef.current;
    prevHasMessagesRef.current = hasMessages;
    if (wasEmpty && hasMessages) {
      requestAnimationFrame(() => {
        lastUserMessageRef.current?.querySelector<HTMLElement>('h2')?.focus();
      });
    }
  }, [hasMessages]);

  // Submitting an aspect selection collapses the directions card to its inline
  // "Erkundet wird: …" summary in place, removing the focused submit button.
  // Move focus onto that summary line so it's read and focus isn't dropped to
  // <body>. (No new message arrives — the directions message is updated in
  // place — so this can't ride the bot-arrival effect.)
  const handleDirectionChoice = useCallback(
    (queryId: string, directions: Array<{ id: string; name: string }>) => {
      onDirectionChoiceAction?.(queryId, directions);
      requestAnimationFrame(() => {
        lastBotMessageRef.current
          ?.querySelector<HTMLElement>('[data-directions-summary]')
          ?.focus();
      });
    },
    [onDirectionChoiceAction],
  );

  // Process-state narration only: thinking/streaming while an answer generates.
  // Arrivals (answers, choice prompt) are owned by the keyed arrival region.
  const statusText = (() => {
    if (isStreaming) return 'KI-Antwort wird geschrieben.';
    if (isThinking) {
      return thinkingMessage ?? 'Nachricht wird verarbeitet...';
    }
    return '';
  })();

  return (
    // One landmark groups the transcript and the composer so a screen reader
    // flips between them without an extra nested-region stop. Focus on
    // exploration start goes to the first message heading (see effect above),
    // not this section, so it needs no tabIndex.
    <section
      aria-label="Gespräch mit der KI"
      className="flex flex-1 flex-col overflow-hidden"
    >
      {/* Process-state announcer: thinking/streaming while an answer generates. */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {statusText}
      </div>
      {/* Arrival announcer. The live region stays mounted; only the inner span
          is keyed, so re-mounting it (even with identical text) registers as a
          content change and re-announces. Keying the region itself would
          replace the node, which screen readers don't reliably read. */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        <span key={arrival.key}>{arrival.text}</span>
      </div>
      {/* The scrollable transcript. No landmark of its own — the per-message
          <h2> headings inside are how screen-reader users jump through it. */}
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
                onDirectionChoiceAction={
                  onDirectionChoiceAction ? handleDirectionChoice : undefined
                }
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
      </div>

      {/* Composer: a plain region inside the shared landmark. Never disabled —
          the user can keep typing while an answer generates or a gate is open. */}
      <div className="sticky bottom-0 w-full border-t bg-background px-4 py-3">
        <div className="mx-auto w-full max-w-xl">
          <ConversationInput
            inputId="chat-input"
            onSubmit={onSendMessageAction}
            placeholder="Stelle eine Frage..."
            suggestedQuestions={suggestedQuestions}
          />
        </div>
      </div>
    </section>
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
