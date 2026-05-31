'use client';

import { cn } from '@/lib/utils';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { ExplorationNode } from '@/modules/guided-exploration/types';
import {
  getBranchProgress,
  isFullyExplored,
} from '@/modules/guided-exploration/utils/tree-helpers';
import { ChevronRight } from 'lucide-react';
import { type ReactNode, useId, useState } from 'react';

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
 * Branch tile rendered inline in the chat. WAI-ARIA disclosure pattern: the
 * h3 wraps a `aria-expanded`/`aria-controls` toggle button so a screen-reader
 * user landing on the heading via the rotor lands *on* the control and can
 * activate it. `expanded` stays controlled so deep-links can force-expand the
 * ancestor chain. The toggle's `after:absolute after:inset-0` stretches the
 * hit area across the header row (only — the panel is a sibling outside the
 * relative container so the overlay never covers the child cards).
 */
export function ExplorationTopicCard({
  node,
  children,
  initialExpanded = false,
}: ExplorationTopicCardProps) {
  const [expanded, setExpanded] = useState(initialExpanded);
  const panelId = useId();
  const progress = getBranchProgress(node);
  const fullyExplored = isFullyExplored(node);

  return (
    <div className="rounded-lg border bg-card shadow-sm">
      <div
        className={cn(
          'relative flex items-start gap-3 rounded-lg p-4 text-left transition-colors',
          'hover:bg-accent has-[:focus-visible]:outline-none has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
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
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => setExpanded((v) => !v)}
                className="text-left after:absolute after:inset-0 focus-visible:outline-none"
              >
                {node.name}
              </button>
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
      </div>

      {expanded && (
        <ul
          id={panelId}
          aria-label={`Unterthemen von ${node.name}`}
          className="mb-4 ml-7 mr-4 flex list-none flex-col gap-2 border-l border-border/60 pl-3"
        >
          {children}
        </ul>
      )}
    </div>
  );
}
