'use client';

import { cn } from '@/lib/utils';
import {
  FollowupMessage,
  InitialContentMessage,
  ThinkingIndicator,
} from '@/modules/guided-exploration/components/conversation';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type {
  Conversation,
  StreamTargetType,
  SubtopicContent,
} from '@/modules/guided-exploration/types';

interface LeafContentProps {
  conversation: Conversation | null;
  isThinking: boolean;
  thinkingMessage?: string | null;
  isStreaming?: boolean;
  streamBuffer?: string;
  /** The type of content being streamed */
  streamingTargetType?: StreamTargetType | null;
  className?: string;
}

export function LeafContent({
  conversation,
  isThinking,
  thinkingMessage,
  isStreaming,
  streamBuffer,
  streamingTargetType,
  className,
}: LeafContentProps) {
  if (!conversation) {
    return null;
  }

  const hasMessages = conversation.messages.length > 0;

  // Only show stream buffer for followup messages (markdown text)
  // For initial_content, the stream contains structured JSON, not displayable text
  const shouldShowStreamBuffer =
    isStreaming && streamBuffer && streamingTargetType === 'followup';

  // Show loading indicator when streaming initial_content
  const isStreamingInitialContent =
    isStreaming && streamingTargetType === 'initial_content';

  return (
    <div className={cn('space-y-6', className)}>
      {conversation.messages.map((message) => {
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
        <PartyMarkedMarkdown onReferenceClick={() => {}} isStreaming>
          {streamBuffer}
        </PartyMarkedMarkdown>
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
