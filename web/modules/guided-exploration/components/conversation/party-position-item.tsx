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
 * Single party position as list item with markdown content
 */
export function PartyPositionItem({
  position,
  citations,
}: PartyPositionItemProps) {
  const { getReferenceName, getReferenceTooltip, handleReferenceClick } =
    useCitationHandlers(citations);

  return (
    <li className="list-none">
      <PartyCard partyId={position.party}>
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <CitationMarkdown
            onReferenceClick={handleReferenceClick}
            getReferenceName={getReferenceName}
            getReferenceTooltip={getReferenceTooltip}
          >
            {position.content}
          </CitationMarkdown>
        </div>
      </PartyCard>
    </li>
  );
}
