'use client';

import { cn } from '@/lib/utils';
import { PartyBadge } from '@/modules/guided-exploration/components/shared/party-badge';
import type { LeafSummary, Subtopic } from '@/modules/guided-exploration/types';
import { Check, ChevronRight } from 'lucide-react';

interface SubtopicItemProps {
  subtopic: Subtopic;
  summary?: LeafSummary | null;
  onClick: () => void;
  className?: string;
}

export function SubtopicItem({
  subtopic,
  summary,
  onClick,
  className,
}: SubtopicItemProps) {
  const isExplored = subtopic.status === 'explored';

  return (
    <button
      type="button"
      onClick={onClick}
      data-subtopic-id={subtopic.id}
      data-status={isExplored ? 'explored' : 'pending'}
      aria-label={`${subtopic.name}${isExplored ? ', erkundet' : ''}`}
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
            isExplored
              ? 'bg-primary text-primary-foreground'
              : 'border-2 border-muted-foreground/30',
          )}
        >
          {isExplored && <Check className="size-3" />}
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <h4 className="font-medium leading-tight">{subtopic.name}</h4>
            <ChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          </div>

          <p className="line-clamp-2 text-sm text-muted-foreground">
            {summary?.overview ?? subtopic.description}
          </p>

          {/* Party badges */}
          {subtopic.parties.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              {subtopic.parties.slice(0, 5).map((party) => (
                <PartyBadge key={party} party={party} />
              ))}
              {subtopic.parties.length > 5 && (
                <span className="text-xs text-muted-foreground">
                  +{subtopic.parties.length - 5}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
