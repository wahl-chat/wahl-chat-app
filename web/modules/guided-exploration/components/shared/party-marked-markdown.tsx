'use client';

import { memo } from 'react';

import {
  hasPartyMarkers,
  parsePartyMarkers,
} from '@/modules/guided-exploration/utils/party-marker-parser';
import { CitationMarkdown } from './citation-markdown';
import { PartyCard } from './party-card';

interface PartyMarkedMarkdownProps {
  /** Markdown content with optional [PARTY:id]...[/PARTY:id] markers */
  children: string;
  /** Callback when a citation reference is clicked */
  onReferenceClick: (id: string) => void;
  /** Get display name for a citation ID */
  getReferenceName?: (id: string) => string | null;
  /** Get tooltip text for a citation ID */
  getReferenceTooltip?: (id: string) => string | null;
  /** Whether the content is currently streaming */
  isStreaming?: boolean;
}

/**
 * Renders markdown content with party markers and inline citations.
 *
 * Supports streaming: handles partial markers and unclosed sections gracefully.
 */
const NonMemoizedPartyMarkedMarkdown = ({
  children,
  onReferenceClick,
  getReferenceName,
  getReferenceTooltip,
}: PartyMarkedMarkdownProps) => {
  if (!hasPartyMarkers(children)) {
    return (
      <div className="prose prose-sm max-w-none text-foreground dark:prose-invert prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground">
        <CitationMarkdown
          onReferenceClick={onReferenceClick}
          getReferenceName={getReferenceName}
          getReferenceTooltip={getReferenceTooltip}
        >
          {children}
        </CitationMarkdown>
      </div>
    );
  }

  const sections = parsePartyMarkers(children);

  return (
    <div className="space-y-4">
      {sections.map((section, index) => {
        if (section.type === 'party' && section.partyId) {
          return (
            <PartyCard
              key={`${section.partyId}-${index}`}
              partyId={section.partyId}
              isStreaming={section.isStreaming}
            >
              <div className="prose prose-sm max-w-none text-foreground dark:prose-invert prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground">
                <CitationMarkdown
                  onReferenceClick={onReferenceClick}
                  getReferenceName={getReferenceName}
                  getReferenceTooltip={getReferenceTooltip}
                >
                  {section.content}
                </CitationMarkdown>
              </div>
            </PartyCard>
          );
        }

        return (
          <div
            key={`${section.type}-${index}`}
            className="prose prose-sm max-w-none text-foreground dark:prose-invert prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground"
          >
            <CitationMarkdown
              onReferenceClick={onReferenceClick}
              getReferenceName={getReferenceName}
              getReferenceTooltip={getReferenceTooltip}
            >
              {section.content}
            </CitationMarkdown>
          </div>
        );
      })}
    </div>
  );
};

export const PartyMarkedMarkdown = memo(
  NonMemoizedPartyMarkedMarkdown,
  (prevProps, nextProps) =>
    prevProps.children === nextProps.children &&
    prevProps.isStreaming === nextProps.isStreaming,
);
