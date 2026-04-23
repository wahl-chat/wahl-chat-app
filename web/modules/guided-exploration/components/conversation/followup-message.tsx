'use client';

import VisuallyHidden from '@/components/visually-hidden';
import { cn } from '@/lib/utils';
import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { Message } from '@/modules/guided-exploration/types';
import { useCitationHandlers } from '@/modules/guided-exploration/utils';

interface FollowupMessageProps {
  message: Message;
  className?: string;
}

/**
 * Renders a followup message (user or assistant)
 * User messages are right-aligned bubbles
 * Assistant messages are left-aligned with markdown and party cards
 */
export function FollowupMessage({ message, className }: FollowupMessageProps) {
  const citations = message.citations ?? [];
  const { getReferenceName, getReferenceTooltip, handleReferenceClick } =
    useCitationHandlers(citations);

  if (typeof message.content !== 'string') {
    return null;
  }

  if (message.role === 'user') {
    return (
      <div className={cn('flex justify-end', className)}>
        <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
          <p className="text-sm">
            <VisuallyHidden>Deine Nachricht: </VisuallyHidden>
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(className)}>
      <VisuallyHidden>Antwort der KI:</VisuallyHidden>
      <PartyMarkedMarkdown
        onReferenceClick={handleReferenceClick}
        getReferenceName={getReferenceName}
        getReferenceTooltip={getReferenceTooltip}
      >
        {message.content}
      </PartyMarkedMarkdown>
      <MessageCitationsList citations={citations} messageId={message.id} />
    </div>
  );
}
