'use client';

import { buildPdfUrl } from '@/lib/utils';
import { CitationMarkdown } from '@/modules/guided-exploration/components/shared/citation-markdown';
import { PartyCard } from '@/modules/guided-exploration/components/shared/party-card';
import type {
  Citation,
  PartyPosition,
} from '@/modules/guided-exploration/types';

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
  const handleReferenceClick = (id: string) => {
    const citation = citations.find((c) => c.id === id);
    if (!citation?.url) {
      console.log('[PartyPositionItem] No URL for citation:', citation);
      return;
    }

    const isPdfLink = citation.url.includes('.pdf');
    if (isPdfLink && citation.page) {
      const url = buildPdfUrl({
        url: citation.url,
        page: citation.page,
        source: citation.party,
        source_document: citation.document,
        document_publish_date: '',
      });
      window.open(url.toString(), '_blank');
    } else {
      window.open(citation.url, '_blank');
    }
  };

  const getReferenceName = (id: string): string | null => {
    // Find the index of this citation to show as number (1-indexed)
    const index = citations.findIndex((c) => c.id === id);
    return index >= 0 ? `${index + 1}` : null;
  };

  const getReferenceTooltip = (id: string): string | null => {
    const citation = citations.find((c) => c.id === id);
    if (!citation) return null;
    // Match regular chat format: "Party - Seite: X"
    console.log(citation);
    return `${citation.party} - Seite: ${citation.page}`;
  };

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
