'use client';

import { CitationMarkdown } from '@/modules/guided-exploration/components/shared/citation-markdown';
import { PartyCard } from '@/modules/guided-exploration/components/shared/party-card';
import type {
  Citation,
  PartyPosition,
} from '@/modules/guided-exploration/types';
import { useCitationHandlers } from '@/modules/guided-exploration/utils';

interface PartyPositionItemProps {
  position: PartyPosition;
  /** All citations for this subtopic (used to resolve inline [index] references) */
  citations: Citation[];
}

/**
 * Single party position card with markdown content. Flows inline within the
 * opening overview turn (no list semantics) so the leaf reads as one message.
 */
export function PartyPositionItem({
  position,
  citations,
}: PartyPositionItemProps) {
  const { getReferenceName, getReferenceTooltip, handleReferenceClick } =
    useCitationHandlers(citations);

  return (
    <PartyCard partyId={position.party}>
      <div className="prose prose-sm max-w-none text-foreground dark:prose-invert prose-p:font-normal prose-p:text-foreground">
        <CitationMarkdown
          onReferenceClick={handleReferenceClick}
          getReferenceName={getReferenceName}
          getReferenceTooltip={getReferenceTooltip}
        >
          {position.content}
        </CitationMarkdown>
      </div>
    </PartyCard>
  );
}
