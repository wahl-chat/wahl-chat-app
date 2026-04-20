'use client';

import type { ExplorationTree } from '@/modules/guided-exploration/types';
import { Search } from 'lucide-react';

interface ExplorationContextBannerProps {
  tree: ExplorationTree;
}

export function ExplorationContextBanner({
  tree,
}: ExplorationContextBannerProps) {
  const directions = tree.selectedDirections;
  const hasDirections = directions && directions.length > 0;

  // Strip "— Fokus: ..." suffix from query for cleaner display
  const query = tree.originalQuery.replace(/\s*—\s*Fokus:.*$/, '');

  return (
    <section
      aria-label="Erkundungskontext"
      className="rounded-lg border bg-muted/30 px-4 py-3"
    >
      <div className="flex items-start gap-2">
        <Search
          aria-hidden="true"
          className="mt-0.5 size-4 shrink-0 text-muted-foreground"
        />
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-medium">{query}</p>
          {hasDirections && (
            <p className="text-xs text-muted-foreground">
              Fokus: {directions.join(' · ')}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
