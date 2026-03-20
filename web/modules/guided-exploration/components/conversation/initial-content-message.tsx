'use client';

import { CitationMarkdown } from '@/modules/guided-exploration/components/shared/citation-markdown';
import type { SubtopicContent } from '@/modules/guided-exploration/types';
import { PartyPositionItem } from './party-position-item';

interface InitialContentMessageProps {
  content: SubtopicContent;
}

/**
 * Renders the initial subtopic content as a styled article/message
 */
export function InitialContentMessage({ content }: InitialContentMessageProps) {
  return (
    <article className="space-y-6">
      <h3 className="font-semibold">Zusammenfassung</h3>
      {/* Summary */}
      <header className="rounded-lg border p-4">
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <CitationMarkdown onReferenceClick={() => {}}>
            {content.summary}
          </CitationMarkdown>
        </div>
      </header>

      {/* Party Positions */}
      {content.partyPositions.length > 0 && (
        <section aria-labelledby="positions-heading">
          <h3 id="positions-heading" className="mb-3 text-base font-semibold">
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
    </article>
  );
}
