'use client';

import { cn } from '@/lib/utils';
import { PartyBadge } from '@/modules/guided-exploration/components/shared/party-badge';
import type {
  ExplorationNode,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import { Check, ChevronRight } from 'lucide-react';

interface SubtopicItemProps {
  node: ExplorationNode;
  summary?: LeafSummary | null;
  onClick: () => void;
  className?: string;
}

const STATUS_LABEL: Record<ExplorationNode['status'], string> = {
  pending: '',
  loaded: ', Inhalte verfügbar',
  started: ', begonnen',
  explored: ', erkundet',
};

export function SubtopicItem({
  node,
  summary,
  onClick,
  className,
}: SubtopicItemProps) {
  const status = node.status;

  return (
    <button
      type="button"
      onClick={onClick}
      data-subtopic-id={node.id}
      data-status={status}
      aria-label={`${node.name}${STATUS_LABEL[status]}`}
      className={cn(
        'w-full rounded-lg border bg-card text-left shadow-sm transition-colors',
        'cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
    >
      <div className="flex items-start gap-3 p-4">
        {/* Status indicator */}
        <div
          className={cn(
            'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full',
            status === 'explored' && 'bg-primary text-primary-foreground',
            status === 'started' && 'border-2 border-primary',
            status === 'loaded' && 'border-2 border-muted-foreground',
            status === 'pending' && 'border-2 border-muted-foreground/30',
          )}
        >
          {status === 'explored' && <Check className="size-3" />}
          {status === 'started' && (
            <span className="size-2 rounded-full bg-primary" />
          )}
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-base font-bold leading-tight text-foreground">
              {node.name}
            </h4>
            <ChevronRight className="mt-0.5 size-4 shrink-0 text-foreground" />
          </div>

          <p className="line-clamp-2 text-sm font-normal text-foreground">
            {summary?.overview ?? node.description}
          </p>

          {/* Party badges */}
          {node.partyIds.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              {node.partyIds.slice(0, 5).map((party) => (
                <PartyBadge key={party} party={party} />
              ))}
              {node.partyIds.length > 5 && (
                <span className="text-xs text-foreground">
                  +{node.partyIds.length - 5}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
