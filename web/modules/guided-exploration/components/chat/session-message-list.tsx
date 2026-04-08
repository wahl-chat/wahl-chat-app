'use client';

import { buildPdfUrl } from '@/lib/utils';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { SessionMessage } from '@/modules/guided-exploration/types';

import { ExplorationCard } from './exploration-card';
import { TopicDirectionsCard } from './topic-directions-card';

interface SessionMessageListProps {
  messages: SessionMessage[];
  onEnterExplorationAction: (explorationId: string) => void;
  onDirectionChoiceAction?: (
    queryId: string,
    directions: Array<{ id: string; name: string }>,
  ) => void;
  isLoading?: boolean;
  /** Index of the last user message (for scroll anchoring) */
  lastUserMessageIndex?: number;
  /** Ref to attach to the last user message element */
  lastUserMessageRef?: React.RefObject<HTMLDivElement | null>;
}

export function SessionMessageList({
  messages,
  onEnterExplorationAction,
  onDirectionChoiceAction,
  isLoading = false,
  lastUserMessageIndex = -1,
  lastUserMessageRef,
}: SessionMessageListProps) {
  return (
    <div className="space-y-4">
      {messages.map((message, index) => {
        if (message.type === 'user') {
          const isLastUser = index === lastUserMessageIndex;
          return (
            <div
              key={message.id}
              ref={isLastUser ? lastUserMessageRef : undefined}
              className="flex justify-end"
            >
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
                {message.content ?? ''}
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

        // topic_directions - show as direction choice cards
        if (message.type === 'topic_directions' && message.directions) {
          return (
            <TopicDirectionsCard
              key={message.id}
              directions={{
                type: 'topic_directions',
                queryId: message.directionsQueryId ?? '',
                originalQuery: '',
                directions: message.directions,
              }}
              onSelectDirections={(directions) =>
                onDirectionChoiceAction?.(
                  message.directionsQueryId ?? '',
                  directions,
                )
              }
              isLoading={isLoading || !onDirectionChoiceAction}
              selectedDirections={message.selectedDirections}
            />
          );
        }

        return null;
      })}
    </div>
  );
}
