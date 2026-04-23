'use client';

import VisuallyHidden from '@/components/visually-hidden';
import { cn } from '@/lib/utils';
import type {
  ExplorationNode,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { StatusDot } from './status-dot';

interface LeafSummaryCardProps {
  node: ExplorationNode;
  summary: LeafSummary | null;
  isActive?: boolean;
  /**
   * When provided the card is interactive (click/keyboard navigates). When
   * omitted the card is static, read-only content — use this for summary
   * surfaces where navigation shouldn't be possible (e.g. study mode).
   */
  onNavigate?: (nodeId: string) => void;
  /**
   * When true (default), show "Noch nicht erkundet" on pending leaves. When
   * false, pending leaves are hidden (the caller should filter them out).
   */
  showPendingHint?: boolean;
  className?: string;
}

export function LeafSummaryCard({
  node,
  summary,
  isActive = false,
  onNavigate,
  showPendingHint = true,
  className,
}: LeafSummaryCardProps) {
  const isExplored = node.status === 'explored';
  const isInteractive = typeof onNavigate === 'function';

  const header = (
    <div className="flex items-start gap-3 p-3">
      <StatusDot
        status={isExplored ? 'explored' : 'pending'}
        className="mt-1 shrink-0"
      />
      <div className="min-w-0 flex-1">
        <h4 className="text-sm font-medium leading-tight">
          {/*
            The interactive variant already carries status in aria-label, so
            we only surface it here for the static variant — otherwise SR
            users would hear "Erkundet" twice.
          */}
          {!isInteractive && (
            <VisuallyHidden>
              {isExplored ? 'Erkundet: ' : 'Nicht erkundet: '}
            </VisuallyHidden>
          )}
          {node.name}
        </h4>
        {!isExplored && showPendingHint && (
          <p className="mt-1 text-xs text-foreground">Noch nicht erkundet</p>
        )}
      </div>
      {isInteractive && (
        <ArrowRight
          className="mt-1 size-4 shrink-0 text-foreground"
          aria-hidden="true"
        />
      )}
    </div>
  );

  const details = isExplored && summary?.overview && (
    <details className="group border-t">
      <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs font-medium text-foreground hover:bg-muted/50">
        <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
        Zusammenfassung
      </summary>
      <div className="px-3 pb-3 pt-1">
        <p className="text-xs leading-relaxed text-foreground">
          {summary.overview}
        </p>
        {summary.keyPoints && summary.keyPoints.length > 0 && (
          <ul className="mt-2 space-y-1">
            {summary.keyPoints.map((point, index) => (
              <li
                key={`${index}-${point.slice(0, 16)}`}
                className="flex items-start gap-1.5 text-xs text-foreground"
              >
                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground/50" />
                {point}
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );

  return (
    <article
      className={cn(
        'overflow-hidden rounded-lg border bg-card shadow-sm',
        isActive && 'ring-2 ring-primary',
        className,
      )}
    >
      {isInteractive ? (
        <button
          type="button"
          onClick={() => onNavigate(node.id)}
          aria-label={`Zu "${node.name}" navigieren${isExplored ? ', erkundet' : ''}`}
          className="block w-full text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {header}
        </button>
      ) : (
        header
      )}
      {details}
    </article>
  );
}
