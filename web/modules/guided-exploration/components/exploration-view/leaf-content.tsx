'use client';

import { useId, useState } from 'react';

import { Button } from '@/components/ui/button';
import VisuallyHidden from '@/components/visually-hidden';
import { cn } from '@/lib/utils';
import {
  FollowupMessage,
  InitialContentMessage,
  ThinkingIndicator,
} from '@/modules/guided-exploration/components/conversation';
import { TopicSwitchCard } from '@/modules/guided-exploration/components/conversation/topic-switch-card';
import { CitationMarkdown } from '@/modules/guided-exploration/components/shared/citation-markdown';
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
  className,
}: LeafContentProps) {
  const [viewMode, setViewMode] = useState<'party' | 'aspect'>('party');
  const summaryHeadingId = useId();

  // Derived up-front so the citation hook below can run before the early
  // return (rules of hooks).
  const initialMessage = conversation?.messages.find(
    (m) => m.type === 'initial_content' && typeof m.content !== 'string',
  );
  const initialContent =
    initialMessage && typeof initialMessage.content !== 'string'
      ? (initialMessage.content as SubtopicContent)
      : null;
  const {
    getReferenceName: getSummaryReferenceName,
    getReferenceTooltip: getSummaryReferenceTooltip,
    handleReferenceClick: handleSummaryReferenceClick,
  } = useCitationHandlers(initialContent?.citations ?? []);

  if (!conversation) {
    return null;
  }

  const hasMessages = conversation.messages.length > 0;

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
          <VisuallyHidden>
            <h3 id={summaryHeadingId}>Antwort der KI:</h3>
          </VisuallyHidden>
          <CitationMarkdown
            onReferenceClick={handleSummaryReferenceClick}
            getReferenceName={getSummaryReferenceName}
            getReferenceTooltip={getSummaryReferenceTooltip}
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
              <FollowupMessage key={message.id} message={message} />
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
              />
            );
          }

          // All others are followup text messages
          return <FollowupMessage key={message.id} message={message} />;
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
          targetNodeName={topicSwitchSuggestion.targetNodeName}
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
        />
      )}

      {/* Loading state when no messages and not streaming yet */}
      {!hasMessages && !isStreaming && !isThinking && (
        <ThinkingIndicator message="Inhalte werden geladen..." />
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
