import { type VoteItem, itemTeaser } from '@/lib/daily/items';
import type { DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { CheckIcon, XIcon } from 'lucide-react';
import { CardFooter, ItemTeaser } from './card-footer';
import { CARD_SURFACE } from './card-styles';
import { useFeedLocale } from './feed-locale';
import { Hemicycle, SeatLegend, VoteGauge } from './hemicycle';
import { TopicMeta } from './topic-chip';

export function OutcomeBadge({
  outcome,
  className,
}: {
  outcome: DigestVote['outcome'];
  className?: string;
}) {
  const { t } = useFeedLocale();
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
      {passed ? t.passed : t.rejected}
    </span>
  );
}

type Props = {
  item: VoteItem;
  onOpen: () => void;
  /** "Passende Abstimmung": the score as a gauge instead of the seat chart. */
  compact?: boolean;
};

function VoteCard({ item, onOpen, compact = false }: Props) {
  const { vote } = item;
  return (
    <article
      data-item-key={item.key}
      className={cn(CARD_SURFACE, 'flex flex-col gap-3 px-4 pb-2 pt-4')}
    >
      <div className="flex items-center justify-between gap-3">
        <TopicMeta topics={vote.topics} />
        <OutcomeBadge outcome={vote.outcome} />
      </div>
      <h3 className="hyphens-auto break-words text-[19px] font-bold leading-snug">
        <button
          type="button"
          onClick={onOpen}
          className="text-left focus-visible:underline focus-visible:outline-none"
        >
          {vote.short_title}
        </button>
      </h3>
      {compact ? (
        <VoteGauge parties={vote.parties} />
      ) : (
        <>
          <Hemicycle parties={vote.parties} className="mx-auto max-w-sm" />
          <SeatLegend parties={vote.parties} />
        </>
      )}
      <ItemTeaser
        text={itemTeaser(item)}
        label={vote.short_title}
        onOpen={onOpen}
      />
      <CardFooter item={item} />
    </article>
  );
}

export default VoteCard;
