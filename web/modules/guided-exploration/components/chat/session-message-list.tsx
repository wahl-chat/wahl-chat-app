'use client';

import { buildPdfUrl } from '@/lib/utils';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { SessionMessage } from '@/modules/guided-exploration/types';

import { ExplorationCard } from './exploration-card';

interface SessionMessageListProps {
  messages: SessionMessage[];
  onEnterExplorationAction: (explorationId: string) => void;
  isLoading?: boolean;
}

export function SessionMessageList({
  messages,
  onEnterExplorationAction,
  isLoading = false,
}: SessionMessageListProps) {
  return (
    <div className="space-y-4">
      {messages.map((message) => {
        if (message.type === 'user') {
          return (
            <div key={message.id} className="flex justify-end">
              <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
                <p className="text-sm">{message.content}</p>
              </div>
            </div>
          );
        }

        if (message.type === 'assistant') {
          const citations = message.citations ?? [];
          console.log(
            '[SessionMessageList] assistant message citations:',
            citations,
          );

          const handleReferenceClick = (id: string) => {
            const citation = citations.find((c) => c.id === id);
            if (!citation?.url) {
              console.log(
                '[SessionMessageList] No URL for citation:',
                citation,
              );
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
            <div key={message.id}>
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

        // exploration_start - show as interactive card
        if (message.type === 'exploration_start') {
          return (
            <ExplorationCard
              key={message.id}
              message={message}
              onEnter={onEnterExplorationAction}
              isLoading={isLoading}
            />
          );
        }

        return null;
      })}
    </div>
  );
}
