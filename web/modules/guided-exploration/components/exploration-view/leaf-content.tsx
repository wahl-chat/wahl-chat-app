'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  FollowupMessage,
  InitialContentMessage,
  ThinkingIndicator,
} from '@/modules/guided-exploration/components/conversation';
import { TopicSwitchCard } from '@/modules/guided-exploration/components/conversation/topic-switch-card';
import { CitationMarkdown } from '@/modules/guided-exploration/components/shared/citation-markdown';
import { leafMessageHeadingId } from '@/modules/guided-exploration/components/shared/message-nav-links';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type {
  Conversation,
  StreamTargetType,
  SubtopicContent,
} from '@/modules/guided-exploration/types';
import {
  useCitationHandlers,
  useStreamingCitationMap,
} from '@/modules/guided-exploration/utils';

import { AspectComparisonView } from './aspect-comparison-view';

interface LeafContentProps {
  conversation: Conversation | null;
  /**
   * Name of the active leaf, used to render a synthetic user message at
   * the top of the conversation ("Gib mir einen Überblick über …") so the
   * leaf reads as a chat thread rather than a static info page.
   */
  leafName?: string | null;
  isThinking: boolean;
  thinkingMessage?: string | null;
  isStreaming?: boolean;
  streamBuffer?: string;
  /** The type of content being streamed */
  streamingTargetType?: StreamTargetType | null;
  /** Topic switch suggestion from routing agent */
  topicSwitchSuggestion?: {
    targetNodeId: string;
    targetNodeName: string;
    message: string;
  } | null;
  onAcceptSwitch?: () => void;
  onDismissSwitch?: () => void;
  /**
   * Hide the "Nach Aspekt" toggle and the aspect comparison view. Used in
   * study mode where the trimmed dataset produces low-quality aspect
   * breakdowns that distract from the conversational summary + party view.
   */
  hideAspectView?: boolean;
  /**
   * Render placeholder cards for parties from the active context that have
   * no position on this subtopic. Used in study mode so participants see
   * all assigned parties.
   */
  showMissingPartiesPlaceholder?: boolean;
  /**
   * id of the most recent assistant turn. Its heading becomes the focus
   * target (`data-leaf-latest-answer`) the sidebar moves focus to when the
   * answer settles.
   */
  latestAnswerId?: string | null;
  /**
   * True when the LLM has proposed closing the leaf, so the composer is
   * replaced by the closure prompt. Re-points the per-message "jump to input"
   * skip-links at the closure prompt's heading (instead of the now-unmounted
   * composer) so they never dead-end.
   */
  showClosurePrompt?: boolean;
  className?: string;
}

export function LeafContent({
  conversation,
  leafName,
  topicSwitchSuggestion,
  onAcceptSwitch,
  onDismissSwitch,
  isThinking,
  thinkingMessage,
  isStreaming,
  streamBuffer,
  streamingTargetType,
  hideAspectView = false,
  showMissingPartiesPlaceholder = false,
  latestAnswerId = null,
  showClosurePrompt = false,
  className,
}: LeafContentProps) {
  const [viewMode, setViewMode] = useState<'party' | 'aspect'>('party');

  // Derived up-front so the citation hook below can run before the early
  // return (rules of hooks).
  const initialMessage = conversation?.messages.find(
    (m) => m.type === 'initial_content' && typeof m.content !== 'string',
  );
  const initialHeadingId = initialMessage
    ? leafMessageHeadingId(initialMessage.id)
    : undefined;

  // Heading id + contextual link text of the message *after* each message, so
  // a "jump to next message" link can skip past the current turn's source list
  // and announce what it lands on. Built over the full message order; works for
  // both the party and aspect views (the latter just omits the opening turn's
  // cards, the ids still resolve).
  const nextNavById = new Map<string, { headingId: string; label: string }>();
  const orderedMessages = conversation?.messages ?? [];
  for (let i = 0; i < orderedMessages.length - 1; i++) {
    const next = orderedMessages[i + 1];
    const label =
      next.type === 'initial_content'
        ? 'Zur Themenzusammenfassung der KI springen'
        : next.role === 'user'
          ? 'Zu deiner nächsten Frage springen'
          : 'Zur nächsten Antwort der KI springen';
    nextNavById.set(orderedMessages[i].id, {
      headingId: leafMessageHeadingId(next.id),
      label,
    });
  }

  // When the LLM proposes closing the leaf, the composer is unmounted and
  // replaced by the closure prompt — so the per-message "jump to input" links
  // must target the prompt's heading instead, or they'd focus nothing.
  const inputId = showClosurePrompt
    ? 'leaf-closure-heading'
    : 'leaf-chat-input';
  const inputLabel = showClosurePrompt
    ? 'Zur Abschlussfrage der KI springen'
    : 'Zum Eingabefeld springen, um eine eigene Frage zu stellen';
  const initialContent =
    initialMessage && typeof initialMessage.content !== 'string'
      ? (initialMessage.content as SubtopicContent)
      : null;
  const {
    getReferenceName: getSummaryReferenceName,
    getReferenceTooltip: getSummaryReferenceTooltip,
    handleReferenceClick: handleSummaryReferenceClick,
  } = useCitationHandlers(initialContent?.citations ?? []);

  // Pre-content state: leaf was just opened, conversation hasn't been
  // hydrated yet (or is empty) and no stream/thinking signal has arrived.
  // Render the synthetic opening user message plus a loading indicator so
  // the sidebar never flashes empty.
  const hasMessages = !!conversation && conversation.messages.length > 0;
  if (!conversation || (!hasMessages && !isStreaming && !isThinking)) {
    return (
      <div className={cn('space-y-6', className)}>
        {leafName && (
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
              <p className="text-sm">
                Gib mir einen Überblick über „{leafName}“.
              </p>
            </div>
          </div>
        )}
        {/* announce={false}: the sidebar's status region owns SR narration
            for the leaf's thinking/streaming state. */}
        <ThinkingIndicator
          message="Inhalte werden geladen..."
          announce={false}
        />
      </div>
    );
  }

  // Show stream buffer only while actively streaming a followup. Previously
  // this also tried to cover the gap between stream_end and the committed
  // conversation_message, but that caused the initial_content summary to
  // linger and render a second time below the structured message.
  const shouldShowStreamBuffer =
    !!streamBuffer && streamingTargetType === 'followup';

  // Show loading indicator when streaming initial_content
  const isStreamingInitialContent =
    isStreaming && streamingTargetType === 'initial_content';

  const hasAspectComparison =
    !hideAspectView &&
    initialContent?.aspectComparison &&
    initialContent.aspectComparison.aspects.length > 0;

  return (
    <div className={cn('space-y-6', className)}>
      {/* Synthetic opening user message — frames the leaf as a chat thread
          where the assistant response below is the answer to this question. */}
      {leafName && (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
            <p className="text-sm">
              Gib mir einen Überblick über „{leafName}“.
            </p>
          </div>
        </div>
      )}

      {/* Summary — rendered as plain assistant message text (no box, no
          heading) so the leaf reads as a real chat reply rather than a
          static info page. The party cards below are part of the same
          assistant turn. */}
      {initialContent?.summary && (
        <div className="prose prose-sm max-w-none text-foreground dark:prose-invert prose-p:font-normal prose-p:text-foreground">
          {/* sr-only heading for the whole opening turn (summary text + party
              cards flow beneath it). Also the focus target when the leaf opens:
              the sidebar focuses [data-leaf-latest-answer] on settle, landing
              on "Initiale Übersicht" — a heading, announced as "Überschrift" in
              every browser (never "group"). */}
          <h2
            id={initialHeadingId}
            data-leaf-latest-answer={
              latestAnswerId && initialMessage?.id === latestAnswerId
                ? ''
                : undefined
            }
            tabIndex={-1}
            className="sr-only outline-none"
          >
            {leafName
              ? `Initiale Übersicht zum Thema „${leafName}“`
              : 'Initiale Übersicht'}
          </h2>
          <CitationMarkdown
            onReferenceClick={handleSummaryReferenceClick}
            getReferenceName={getSummaryReferenceName}
            getReferenceTooltip={getSummaryReferenceTooltip}
            baseHeadingLevel={2}
          >
            {initialContent.summary}
          </CitationMarkdown>
        </div>
      )}

      {/* View toggle — only show when aspect comparison data is available */}
      {hasAspectComparison && (
        <div
          role="group"
          aria-label="Ansicht umschalten"
          className="flex items-center gap-1 rounded-lg border p-1"
        >
          <Button
            variant={viewMode === 'party' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('party')}
            aria-pressed={viewMode === 'party'}
            className="flex-1 text-xs"
          >
            Nach Partei
          </Button>
          <Button
            variant={viewMode === 'aspect' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('aspect')}
            aria-pressed={viewMode === 'aspect'}
            className="flex-1 text-xs"
          >
            Nach Aspekt
          </Button>
        </div>
      )}

      {/* Aspect comparison view */}
      {viewMode === 'aspect' && hasAspectComparison && initialContent && (
        <>
          {initialContent.aspectComparison && (
            <AspectComparisonView
              comparison={initialContent.aspectComparison}
            />
          )}
          {/* Follow-up messages still shown below */}
          {conversation.messages
            .filter((m) => m.type !== 'initial_content')
            .map((message) => (
              <FollowupMessage
                key={message.id}
                message={message}
                isLatestAnswer={message.id === latestAnswerId}
                nextHeadingId={nextNavById.get(message.id)?.headingId ?? null}
                nextLabel={nextNavById.get(message.id)?.label}
                inputId={inputId}
                inputLabel={inputLabel}
              />
            ))}
        </>
      )}

      {/* Party view (default) */}
      {viewMode === 'party' &&
        conversation.messages.map((message) => {
          // First message is always initial_content with SubtopicContent
          if (
            message.type === 'initial_content' &&
            typeof message.content !== 'string'
          ) {
            return (
              <InitialContentMessage
                key={message.id}
                messageId={message.id}
                content={message.content as SubtopicContent}
                showMissingPartiesPlaceholder={showMissingPartiesPlaceholder}
                nextHeadingId={nextNavById.get(message.id)?.headingId ?? null}
                nextLabel={nextNavById.get(message.id)?.label}
                inputId={inputId}
                inputLabel={inputLabel}
              />
            );
          }

          // All others are followup text messages
          return (
            <FollowupMessage
              key={message.id}
              message={message}
              isLatestAnswer={message.id === latestAnswerId}
              nextHeadingId={nextNavById.get(message.id)?.headingId ?? null}
              nextLabel={nextNavById.get(message.id)?.label}
              inputId={inputId}
              inputLabel={inputLabel}
            />
          );
        })}

      {/* Streaming content while loading - only for followup messages.
          Not a live region — per-token aria-live floods SR with partial
          words. Start/end announcement is handled elsewhere. */}
      {shouldShowStreamBuffer && (
        <div aria-hidden="true">
          <StreamingBuffer content={streamBuffer ?? ''} />
        </div>
      )}

      {/* Topic switch suggestion */}
      {topicSwitchSuggestion && onAcceptSwitch && onDismissSwitch && (
        <TopicSwitchCard
          message={topicSwitchSuggestion.message}
          onAccept={onAcceptSwitch}
          onDismiss={onDismissSwitch}
        />
      )}

      {/* Thinking indicator - show when thinking and not streaming followup */}
      {(isThinking || isStreamingInitialContent) && !shouldShowStreamBuffer && (
        <ThinkingIndicator
          message={
            isStreamingInitialContent
              ? 'Inhalte werden generiert...'
              : (thinkingMessage ?? undefined)
          }
          announce={false}
        />
      )}
    </div>
  );
}

function StreamingBuffer({ content }: { content: string }) {
  const { getReferenceName } = useStreamingCitationMap(content);

  return (
    <PartyMarkedMarkdown
      onReferenceClick={() => {}}
      getReferenceName={getReferenceName}
      isStreaming
    >
      {content}
    </PartyMarkedMarkdown>
  );
}
