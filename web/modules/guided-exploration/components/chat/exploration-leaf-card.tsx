'use client';

import VisuallyHidden from '@/components/visually-hidden';
import { cn } from '@/lib/utils';
import { PartyBadge } from '@/modules/guided-exploration/components/shared/party-badge';
import type { ExplorationNode } from '@/modules/guided-exploration/types';
import { Check, ChevronRight } from 'lucide-react';

interface ExplorationLeafCardProps {
  node: ExplorationNode;
  onOpen?: (leafId: string) => void;
}

const MAX_VISIBLE_BADGES = 5;

/**
 * Leaf tile rendered inline in the chat. Clicking opens the right-side
 * leaf sidebar via `onOpen`. Replaces the v3 plain-button row with a
 * proper white card matching the v2 SubtopicItem look.
 */
export function ExplorationLeafCard({
  node,
  onOpen,
}: ExplorationLeafCardProps) {
  const isExplored = node.status === 'explored';
  const isStarted = node.status === 'started';

  const statusLabel = isExplored
    ? 'erkundet'
    : isStarted
      ? 'in Bearbeitung'
      : 'noch nicht erkundet';

  const description = node.description;

  const visibleParties = node.partyIds.slice(0, MAX_VISIBLE_BADGES);
  const overflowCount = Math.max(0, node.partyIds.length - MAX_VISIBLE_BADGES);

  return (
    <button
      type="button"
      // Stable id so closing a leaf can move focus straight back to this card.
      id={`leaf-card-${node.id}`}
      // Terse accessible name: identity + status only. The description and
      // party badges stay visual; folding them into the name makes every card
      // a wall of speech to arrow past, and the close flow re-reads it on
      // return. "What just happened" is reported separately by the close
      // announcer's live region, not by this label.
      aria-label={`${node.name}, ${statusLabel}`}
      onClick={() => onOpen?.(node.id)}
      disabled={!onOpen}
      className={cn(
        'flex w-full items-start gap-3 rounded-lg border bg-card p-4 text-left shadow-sm transition-colors',
        'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:opacity-60',
      )}
    >
      <span className="mt-0.5 flex shrink-0 items-center justify-center">
        <LeafStatusIcon status={node.status} />
      </span>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h4 className="text-sm font-semibold leading-tight text-foreground">
          {node.name}
        </h4>
        {description && (
          <p className="line-clamp-2 text-sm font-normal text-foreground">
            {description}
          </p>
        )}
        {visibleParties.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {visibleParties.map((party) => (
              <PartyBadge key={party} party={party} className="size-7" />
            ))}
            {overflowCount > 0 && (
              <span className="inline-flex size-7 items-center justify-center rounded-md border bg-muted text-xs font-medium text-foreground">
                <span aria-hidden="true">+{overflowCount}</span>
                <VisuallyHidden>
                  {overflowCount} weitere Parteien
                </VisuallyHidden>
              </span>
            )}
          </div>
        )}
      </div>

      <ChevronRight
        aria-hidden="true"
        className="mt-1 size-4 shrink-0 text-foreground"
      />
    </button>
  );
}

function LeafStatusIcon({ status }: { status: ExplorationNode['status'] }) {
  if (status === 'explored') {
    return (
      <span
        aria-hidden="true"
        className="flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
      >
        <Check className="size-3" />
      </span>
    );
  }
  if (status === 'started') {
    // Static "in progress" indicator — was a spinning Loader2, but that
    // reads as "loading right now" and persists across reloads for any
    // leaf the user opened without finishing.
    return (
      <span
        aria-hidden="true"
        className="flex size-5 items-center justify-center"
      >
        <span className="flex size-4 items-center justify-center rounded-full border-2 border-primary">
          <span className="size-1.5 rounded-full bg-primary" />
        </span>
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className="flex size-5 items-center justify-center"
    >
      <span className="size-2 rounded-full border border-muted-foreground/40" />
    </span>
  );
}
