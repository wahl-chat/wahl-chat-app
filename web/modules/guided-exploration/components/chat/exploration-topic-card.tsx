'use client';

import { cn } from '@/lib/utils';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { ExplorationNode } from '@/modules/guided-exploration/types';
import {
  getBranchProgress,
  isFullyExplored,
} from '@/modules/guided-exploration/utils/tree-helpers';
import { ChevronRight } from 'lucide-react';
import { type ReactNode, useState } from 'react';

interface ExplorationTopicCardProps {
  node: ExplorationNode;
  /**
   * Expanded body. Caller is responsible for wrapping each child in a
   * `<li>` with a stable key — this card just renders the surrounding `<ul>`.
   */
  children: ReactNode;
  /** When true (deep-link), card starts expanded. */
  initialExpanded?: boolean;
}

/**
 * Branch tile rendered inline in the chat. Native `<details>/<summary>`
 * disclosure with controlled `open` so deep-links can force-expand the
 * ancestor chain. The visible h3 + description + progress label form the
 * summary's accessible name — no aria overrides needed.
 */
export function ExplorationTopicCard({
  node,
  children,
  initialExpanded = false,
}: ExplorationTopicCardProps) {
  const [expanded, setExpanded] = useState(initialExpanded);
  const progress = getBranchProgress(node);
  const fullyExplored = isFullyExplored(node);

  return (
    <details
      open={expanded}
      onToggle={(e) => setExpanded(e.currentTarget.open)}
      className="rounded-lg border bg-card shadow-sm"
    >
      <summary
        aria-expanded={expanded}
        className={cn(
          'group flex cursor-pointer list-none items-start gap-3 rounded-lg p-4 text-left transition-colors',
          'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          '[&::-webkit-details-marker]:hidden',
        )}
      >
        <ChevronRight
          aria-hidden="true"
          className={cn(
            'mt-1 size-4 shrink-0 text-foreground transition-transform duration-150',
            expanded && 'rotate-90',
          )}
        />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-sm font-semibold leading-tight text-foreground">
              {node.name}
            </h3>
            {fullyExplored && (
              <span className="shrink-0 rounded bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                Fertig
              </span>
            )}
          </div>
          {node.description && (
            <p className="line-clamp-2 text-sm font-normal text-foreground">
              {node.description}
            </p>
          )}
          <ProgressIndicator
            explored={progress.explored}
            total={progress.total}
          />
        </div>
      </summary>

      <ul className="mb-4 ml-7 mr-4 flex list-none flex-col gap-2 border-l border-border/60 pl-3">
        {children}
      </ul>
    </details>
  );
}
