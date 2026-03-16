'use client';

import { buildPdfUrl } from '@/lib/utils';
import { cn } from '@/lib/utils';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { Message } from '@/modules/guided-exploration/types';

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
  // Only handle string content for followup messages
  if (typeof message.content !== 'string') {
    return null;
  }

  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className={cn('flex justify-end', className)}>
        <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message with citations
  const citations = message.citations ?? [];

  const handleReferenceClick = (id: string) => {
    const citation = citations.find((c) => c.id === id);
    if (!citation?.url) {
      console.log('[FollowupMessage] No URL for citation:', citation);
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
    return `${citation.party} - Seite: ${citation.page}`;
  };

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
