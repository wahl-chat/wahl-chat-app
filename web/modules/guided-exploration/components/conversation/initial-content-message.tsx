'use client';

import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import type { SubtopicContent } from '@/modules/guided-exploration/types';
import { PartyPositionItem } from './party-position-item';

interface InitialContentMessageProps {
  content: SubtopicContent;
  messageId: string;
}

/**
 * Renders the initial subtopic content as a styled article/message
 */
export function InitialContentMessage({
  content,
  messageId,
}: InitialContentMessageProps) {
  return (
    <article className="space-y-6">
      {/* Party Positions */}
      {content.partyPositions.length > 0 && (
        <section aria-labelledby="positions-heading">
          <h3
            id="positions-heading"
            className="mb-3 text-lg font-bold text-foreground"
          >
            Parteipositionen
          </h3>
          <ul className="space-y-4">
            {content.partyPositions.map((position) => (
              <PartyPositionItem
                key={position.party}
                position={position}
                citations={content.citations}
              />
            ))}
          </ul>
        </section>
      )}

      <MessageCitationsList
        citations={content.citations}
        messageId={messageId}
      />
    </article>
  );
}
