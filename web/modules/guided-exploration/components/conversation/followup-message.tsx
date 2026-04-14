'use client';

import { cn } from '@/lib/utils';
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
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn(className)}>
      <PartyMarkedMarkdown
        onReferenceClick={handleReferenceClick}
        getReferenceName={getReferenceName}
        getReferenceTooltip={getReferenceTooltip}
      >
        {message.content}
      </PartyMarkedMarkdown>
    </div>
  );
}
