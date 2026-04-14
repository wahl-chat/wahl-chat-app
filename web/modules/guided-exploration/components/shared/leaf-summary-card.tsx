'use client';

import { cn } from '@/lib/utils';
import type {
  ExplorationNode,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { nanoid } from 'nanoid';
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

  const handleClick = isInteractive ? () => onNavigate(node.id) : undefined;

  const handleKeyDown = isInteractive
    ? (e: React.KeyboardEvent<HTMLElement>) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onNavigate(node.id);
        }
      }
    : undefined;

  return (
    <article
      className={cn(
        'rounded-lg border bg-card shadow-sm transition-colors',
        isInteractive && 'cursor-pointer hover:bg-accent',
        isActive && 'ring-2 ring-primary',
        className,
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      aria-label={
        isInteractive
          ? `Zu "${node.name}" navigieren${isExplored ? ', erkundet' : ''}`
          : undefined
      }
    >
      <div className="flex items-start gap-3 p-3">
        <StatusDot
          status={isExplored ? 'explored' : 'pending'}
          className="mt-1 shrink-0"
        />
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium leading-tight">{node.name}</h4>
          {!isExplored && showPendingHint && (
            <p className="mt-1 text-xs text-muted-foreground">
              Noch nicht erkundet
            </p>
          )}
        </div>
        {isInteractive && (
          <ArrowRight
            className="mt-1 size-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
        )}
      </div>

      {isExplored && summary?.overview && (
        <details
          className="group border-t"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/50">
            <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
            Zusammenfassung
          </summary>
          <div className="px-3 pb-3 pt-1">
            <p className="text-xs leading-relaxed text-muted-foreground">
              {summary.overview}
            </p>
            {summary.keyPoints && summary.keyPoints.length > 0 && (
              <ul className="mt-2 space-y-1">
                {summary.keyPoints.map((point) => (
                  <li
                    key={nanoid()}
                    className="flex items-start gap-1.5 text-xs text-muted-foreground"
                  >
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground/50" />
                    {point}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </details>
      )}
    </article>
  );
}
