'use client';

import { cn } from '@/lib/utils';
import { firstSentence } from '@/modules/guided-exploration/components/chat/session-message-list';
import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import { leafMessageHeadingId } from '@/modules/guided-exploration/components/shared/message-nav-links';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { Message } from '@/modules/guided-exploration/types';
import { useCitationHandlers } from '@/modules/guided-exploration/utils';

interface FollowupMessageProps {
  message: Message;
  className?: string;
  /**
   * Marks this as the most recent assistant answer in the leaf. Its heading
   * becomes the programmatic focus target (`data-leaf-latest-answer`,
   * `tabIndex={-1}`) the sidebar moves focus to once the answer settles.
   */
  isLatestAnswer?: boolean;
  /**
   * Content rendered at the end of this turn — after the answer, before the
   * sources. Used to attach the leaf closure prompt to the latest turn so it
   * reads right after the answer.
   */
  trailing?: React.ReactNode;
}

/**
 * Renders a followup message (user or assistant)
 * User messages are right-aligned bubbles
 * Assistant messages are left-aligned with markdown and party cards
 */
export function FollowupMessage({
  message,
  className,
  isLatestAnswer = false,
  trailing,
}: FollowupMessageProps) {
  const citations = message.citations ?? [];
  const { getReferenceName, getReferenceTooltip, handleReferenceClick } =
    useCitationHandlers(citations);

  if (typeof message.content !== 'string') {
    return null;
  }

  if (message.role === 'user') {
    return (
      <div className={cn('flex justify-end', className)}>
        {/* sr-only heading: content-bearing rotor anchor and the focus target
            for "jump to next message" links pointing here. */}
        <h2
          id={leafMessageHeadingId(message.id)}
          tabIndex={-1}
          className="sr-only outline-none"
        >
          {`Du: ${firstSentence(message.content, 100)}`}
        </h2>
        <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  const snippet = firstSentence(message.content, 100);

  return (
    <div className={cn(className)}>
      {/* sr-only heading: content-bearing rotor anchor for jumping between
          past answers, and the focus target for the newest answer. The sidebar
          focuses [data-leaf-latest-answer] on settle, landing on "KI: …" — a
          heading, announced as "Überschrift" in every browser (never "group"). */}
      <h2
        id={leafMessageHeadingId(message.id)}
        className="sr-only outline-none"
        data-leaf-latest-answer={isLatestAnswer ? '' : undefined}
        tabIndex={-1}
      >
        {snippet ? `KI: ${snippet}` : 'Antwort der KI'}
      </h2>
      <PartyMarkedMarkdown
        onReferenceClick={handleReferenceClick}
        getReferenceName={getReferenceName}
        getReferenceTooltip={getReferenceTooltip}
        baseHeadingLevel={2}
      >
        {message.content}
      </PartyMarkedMarkdown>
      {trailing}

      <MessageCitationsList citations={citations} messageId={message.id} />
    </div>
  );
}
