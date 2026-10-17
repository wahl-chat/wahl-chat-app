import type { VoteItem } from '@/lib/daily/items';
import type { DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { CheckIcon, ChevronRightIcon, XIcon } from 'lucide-react';
import { CARD_SURFACE, FOCUS_RING } from './card-styles';
import { Hemicycle, SeatLegend, VoteGauge } from './hemicycle';
import InterestFeedback from './interest-feedback';
import { TopicMeta } from './topic-chip';

export function OutcomeBadge({
  outcome,
  className,
}: {
  outcome: DigestVote['outcome'];
  className?: string;
}) {
  if (!outcome) {
    return null;
  }
  const passed = outcome === 'angenommen';
  const Icon = passed ? CheckIcon : XIcon;
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full px-3 py-1 text-sm font-semibold',
        passed
          ? 'bg-[var(--daily-yes-bg)] text-[var(--daily-yes)]'
          : 'bg-[var(--daily-no-bg)] text-[var(--daily-no)]',
        className,
      )}
    >
      <Icon className="size-3.5" strokeWidth={3} aria-hidden />
      {passed ? 'Angenommen' : 'Abgelehnt'}
    </span>
  );
}

/** "Mehr erfahren ›": the whole card opens the detail, this is its label. */
export function MoreLink({
  onOpen,
  label,
}: {
  onOpen: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Mehr erfahren: ${label}`}
      className={cn(
        FOCUS_RING,
        'flex min-h-10 shrink-0 items-center gap-1 rounded-md text-[15px] font-semibold',
      )}
    >
      Mehr erfahren <ChevronRightIcon className="size-4" aria-hidden />
    </button>
  );
}

type Props = {
  item: VoteItem;
  onOpen: () => void;
  /** "Passende Abstimmung": no chart, only the score. */
  compact?: boolean;
};

function VoteCard({ item, onOpen, compact = false }: Props) {
  const { vote } = item;
  return (
    <article
      data-item-key={item.key}
      className={cn(CARD_SURFACE, 'flex flex-col gap-3 p-4')}
    >
      <div className="flex items-center justify-between gap-3">
        <TopicMeta topics={vote.topics} short />
        <OutcomeBadge outcome={vote.outcome} />
      </div>
      <h3 className="hyphens-auto break-words text-[19px] font-bold leading-snug">
        {vote.short_title}
      </h3>
      {compact ? (
        <div className="flex items-end justify-between gap-3">
          <VoteGauge parties={vote.parties} />
          <MoreLink onOpen={onOpen} label={vote.short_title} />
        </div>
      ) : (
        <>
          <Hemicycle parties={vote.parties} className="mx-auto max-w-sm" />
          <SeatLegend parties={vote.parties} />
          <div className="flex items-center gap-2 border-t border-[var(--daily-border)] pt-3">
            <MoreLink onOpen={onOpen} label={vote.short_title} />
            <InterestFeedback itemKey={item.key} grouped className="flex-1" />
          </div>
        </>
      )}
    </article>
  );
}

export default VoteCard;
