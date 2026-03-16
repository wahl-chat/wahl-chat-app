'use client';

import { memo } from 'react';

import {
  hasPartyMarkers,
  parsePartyMarkers,
  stripPartyMarkers,
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
 *
 * Format:
 * ```
 * Intro text...
 *
 * [PARTY:spd]
 * SPD content with [0] citations...
 * [/PARTY:spd]
 *
 * [PARTY:cdu]
 * CDU content with [1] citations...
 * [/PARTY:cdu]
 *
 * Conclusion text...
 * ```
 */
const NonMemoizedPartyMarkedMarkdown = ({
  children,
  onReferenceClick,
  getReferenceName,
  getReferenceTooltip,
  isStreaming,
}: PartyMarkedMarkdownProps) => {
  // If no party markers, render as plain citation markdown
  if (!hasPartyMarkers(children)) {
    return (
      <div className="prose prose-sm max-w-none dark:prose-invert">
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

  // Parse sections
  const sections = parsePartyMarkers(children);

  // Screen reader only: full plain text without markers
  const plainText = stripPartyMarkers(children);

  return (
    <div className="space-y-4">
      {/* Screen reader: full text version */}
      <div className="sr-only" aria-live={isStreaming ? 'polite' : 'off'}>
        {plainText}
      </div>

      {/* Visual: sectioned view with party cards */}
      <div className="space-y-4" aria-hidden="true">
        {sections.map((section, index) => {
          if (section.type === 'party' && section.partyId) {
            return (
              <PartyCard
                key={`${section.partyId}-${index}`}
                partyId={section.partyId}
                isStreaming={section.isStreaming}
              >
                <div className="prose prose-sm max-w-none dark:prose-invert">
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

          // Intro or conclusion - render as plain markdown
          return (
            <div
              key={`${section.type}-${index}`}
              className="prose prose-sm max-w-none dark:prose-invert"
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
    </div>
  );
};

export const PartyMarkedMarkdown = memo(
  NonMemoizedPartyMarkedMarkdown,
  (prevProps, nextProps) =>
    prevProps.children === nextProps.children &&
    prevProps.isStreaming === nextProps.isStreaming,
);
