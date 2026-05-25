'use client';

import { CitationMarkdown } from '@/modules/guided-exploration/components/shared/citation-markdown';
import { PartyCard } from '@/modules/guided-exploration/components/shared/party-card';
import type { ExplorationOverview } from '@/modules/guided-exploration/types';
import { useCallback, useId } from 'react';

interface ExplorationOverviewCardProps {
  overview: ExplorationOverview;
  /**
   * Optional id to attach to the intro paragraph. When provided, this
   * element doubles as the accessible label for an enclosing landmark.
   */
  headingId?: string;
}

export function ExplorationOverviewCard({
  overview,
  headingId,
}: ExplorationOverviewCardProps) {
  const fallbackHeadingId = useId();
  const introId = headingId ?? fallbackHeadingId;
  // The intro paragraph never contains citations; the markdown renderer
  // still requires the callback, so we hand it a no-op.
  const noopReferenceClick = useCallback(() => {}, []);

  return (
    <div className="flex flex-col gap-3">
      <div
        id={introId}
        className="prose prose-sm max-w-none text-sm text-foreground dark:prose-invert prose-p:text-foreground prose-strong:font-semibold prose-strong:text-foreground"
      >
        <CitationMarkdown onReferenceClick={noopReferenceClick}>
          {overview.introParagraph}
        </CitationMarkdown>
      </div>

      {overview.partySummaries.length > 0 && (
        <ul
          aria-label="Zusammenfassung nach Parteien"
          className="flex list-none flex-col gap-2 pl-0"
        >
          {overview.partySummaries.map((entry) => (
            <li key={entry.partyId}>
              <PartyCard partyId={entry.partyId}>
                <p className="text-sm text-foreground whitespace-pre-line">
                  {entry.summary}
                </p>
              </PartyCard>
            </li>
          ))}
        </ul>
      )}

      <p className="text-sm text-foreground">
        Klicke dich hier durch die einzelnen Themen, um zu jeweils einem Thema
        zu chatten.
      </p>
    </div>
  );
}
