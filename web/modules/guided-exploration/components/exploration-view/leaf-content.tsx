'use client';

import { useMemo } from 'react';

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

  // Show stream buffer for followup messages while streaming OR while buffer
  // still has content (covers the gap between stream_end and conversation_message)
  const isFollowupStream =
    streamingTargetType === 'followup' || (!isStreaming && streamBuffer);
  const shouldShowStreamBuffer = !!streamBuffer && isFollowupStream;

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
        <StreamingBuffer content={streamBuffer ?? ''} />
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

/**
 * Renders streaming buffer with citation IDs mapped to sequential numbers.
 * Extracts all unique [party-hex] patterns and assigns 1, 2, 3...
 */
function StreamingBuffer({ content }: { content: string }) {
  // Build a stable mapping of citation IDs to sequential numbers
  const citationMap = useMemo(() => {
    const map = new Map<string, number>();
    // Match citation IDs like [afd-3740c308] or [spd-abc123, cdu-def456]
    const matches = content.matchAll(/\[([\w.-]+(?:\s*,\s*[\w.-]+)*)\]/g);
    for (const match of matches) {
      const ids = match[1].split(/\s*,\s*/);
      for (const id of ids) {
        if (!map.has(id) && id.includes('-')) {
          map.set(id, map.size + 1);
        }
      }
    }
    return map;
  }, [content]);

  const getReferenceName = (id: string): string | null => {
    const num = citationMap.get(id);
    return num !== undefined ? `${num}` : null;
  };

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
