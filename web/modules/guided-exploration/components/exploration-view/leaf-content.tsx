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
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type {
  Conversation,
  StreamTargetType,
  SubtopicContent,
} from '@/modules/guided-exploration/types';
import { useStreamingCitationMap } from '@/modules/guided-exploration/utils';

import { AspectComparisonView } from './aspect-comparison-view';

interface LeafContentProps {
  conversation: Conversation | null;
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
  className?: string;
}

export function LeafContent({
  conversation,
  topicSwitchSuggestion,
  onAcceptSwitch,
  onDismissSwitch,
  isThinking,
  thinkingMessage,
  isStreaming,
  streamBuffer,
  streamingTargetType,
  className,
}: LeafContentProps) {
  const [viewMode, setViewMode] = useState<'party' | 'aspect'>('party');

  if (!conversation) {
    return null;
  }

  const hasMessages = conversation.messages.length > 0;

  // Show stream buffer for followup messages while streaming OR while buffer
  // still has content (covers the gap between stream_end and conversation_message)
  const isFollowupStream =
    streamingTargetType === 'followup' || (!isStreaming && streamBuffer);
  const shouldShowStreamBuffer = !!streamBuffer && isFollowupStream;

  // Show loading indicator when streaming initial_content
  const isStreamingInitialContent =
    isStreaming && streamingTargetType === 'initial_content';

  // Find initial content for aspect comparison
  const initialMessage = conversation.messages.find(
    (m) => m.type === 'initial_content' && typeof m.content !== 'string',
  );
  const initialContent =
    initialMessage && typeof initialMessage.content !== 'string'
      ? (initialMessage.content as SubtopicContent)
      : null;
  const hasAspectComparison =
    initialContent?.aspectComparison &&
    initialContent.aspectComparison.aspects.length > 0;

  return (
    <div className={cn('space-y-6', className)}>
      {/* View toggle — only show when aspect comparison data is available */}
      {hasAspectComparison && (
        <div className="flex items-center gap-1 rounded-lg border p-1">
          <Button
            variant={viewMode === 'party' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('party')}
            className="flex-1 text-xs"
          >
            Nach Partei
          </Button>
          <Button
            variant={viewMode === 'aspect' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('aspect')}
            className="flex-1 text-xs"
          >
            Nach Aspekt
          </Button>
        </div>
      )}

      {/* Aspect comparison view */}
      {viewMode === 'aspect' && hasAspectComparison && initialContent && (
        <>
          {/* Summary still shown above the comparison */}
          {initialContent.summary && (
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">
                {initialContent.summary}
              </p>
            </div>
          )}
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
                content={message.content as SubtopicContent}
              />
            );
          }

          // All others are followup text messages
          return <FollowupMessage key={message.id} message={message} />;
        })}

      {/* Streaming content while loading - only for followup messages */}
      {shouldShowStreamBuffer && (
        <StreamingBuffer content={streamBuffer ?? ''} />
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
