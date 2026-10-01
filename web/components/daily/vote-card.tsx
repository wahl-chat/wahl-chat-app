import { isCloseVote, voteTotals } from '@/lib/daily/hemicycle';
import { STAMP_COLORS } from '@/lib/daily/palette';
import type { DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { VoteIcon } from 'lucide-react';
import { CARD_INTERACTIVE, MUTED_TEXT } from './card-styles';
import { Hemicycle, VoteTally } from './hemicycle';
import TopicChip from './topic-chip';

/** Rubber-stamp look: double frame in the outcome colour, slightly askew. */
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
  const color = STAMP_COLORS[outcome];
  return (
    <span
      className={cn(
        '-rotate-3 rounded-[3px] border-4 border-double bg-[var(--daily-surface)] px-2 py-0.5 font-display text-sm font-black uppercase tracking-[0.12em] opacity-95',
        className,
      )}
      style={{ borderColor: color, color }}
    >
      {outcome === 'angenommen' ? 'Angenommen' : 'Abgelehnt'}
    </span>
  );
}

export function CloseVoteSticker({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'rotate-2 border-2 border-[#1A1A1A] px-1.5 py-0.5 text-[11px] font-black uppercase tracking-wider text-[#1A1A1A] shadow-[2px_2px_0_0_#1A1A1A]',
        className,
      )}
      style={{ backgroundColor: STAMP_COLORS.close }}
    >
      Knapp!
    </span>
  );
}

export function VoteTotalsLine({ vote }: { vote: DigestVote }) {
  const totals = voteTotals(vote.parties);
  return (
    <p className={cn('text-xs font-medium tabular-nums', MUTED_TEXT)}>
      {totals.yes} Ja · {totals.no} Nein · {totals.abstain} Enthalten ·{' '}
      {totals.absent} Abwesend
    </p>
  );
}

type Props = {
  vote: DigestVote;
  onOpen: () => void;
};

function VoteCard({ vote, onOpen }: Props) {
  const close = isCloseVote(vote.parties);
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(CARD_INTERACTIVE, 'relative flex h-full w-full flex-col')}
    >
      {/* Same masthead strip as the plenary card; the stamps sit on top of it. */}
      <div className="flex items-center gap-1.5 rounded-t-[4px] bg-[var(--daily-ink)] px-5 py-2 text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--daily-canvas)]">
        <VoteIcon className="size-3.5" />
        Abstimmung
      </div>
      <div className="absolute -top-3.5 right-3 flex items-start gap-2">
        {close && <CloseVoteSticker className="mt-1" />}
        <OutcomeBadge outcome={vote.outcome} />
      </div>
      <div className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-1.5">
          {vote.topics.map((topic) => (
            <TopicChip key={topic} topic={topic} />
          ))}
        </div>
        <h4 className="font-display text-xl font-extrabold leading-tight">
          {vote.short_title}
        </h4>
        <Hemicycle parties={vote.parties} className="mx-auto max-w-96" />
        <VoteTally parties={vote.parties} />
        <VoteTotalsLine vote={vote} />
      </div>
    </button>
  );
}

export default VoteCard;
