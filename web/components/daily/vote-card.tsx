import { voteTotals } from '@/lib/daily/hemicycle';
import { sortBySeating } from '@/lib/daily/seating-order';
import type { DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { CARD_INTERACTIVE } from './card-styles';
import { Hemicycle } from './hemicycle';
import TopicChip from './topic-chip';

export function OutcomeBadge({ outcome }: { outcome: DigestVote['outcome'] }) {
  if (!outcome) {
    return null;
  }
  return (
    <span
      className={cn(
        'rounded-md px-2 py-0.5 text-xs font-semibold',
        outcome === 'angenommen'
          ? 'bg-[hsl(var(--chart-yes)/0.15)] text-green-700 dark:text-green-400'
          : 'bg-[hsl(var(--chart-no)/0.15)] text-red-700 dark:text-red-400',
      )}
    >
      {outcome === 'angenommen' ? 'Angenommen' : 'Abgelehnt'}
    </span>
  );
}

export function VoteTotalsLine({ vote }: { vote: DigestVote }) {
  const totals = voteTotals(vote.parties);
  return (
    <p className="text-xs tabular-nums text-muted-foreground">
      {totals.yes} Ja · {totals.no} Nein · {totals.abstain} Enthalten ·{' '}
      {totals.absent} Abwesend
    </p>
  );
}

export function PartyKey({ vote }: { vote: DigestVote }) {
  return (
    <ul className="flex flex-wrap gap-x-2.5 gap-y-1 text-xs text-muted-foreground">
      {sortBySeating(vote.parties).map((party) => (
        <li key={party.party_id} className="flex items-center gap-1">
          <span
            className="inline-block h-1.5 w-3 rounded-sm border border-border"
            style={{ backgroundColor: party.color }}
          />
          {party.name}
        </li>
      ))}
    </ul>
  );
}

type Props = {
  vote: DigestVote;
  onOpen: () => void;
};

function VoteCard({ vote, onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(CARD_INTERACTIVE, 'flex w-full flex-col gap-2 p-4')}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        {vote.topics.map((topic) => (
          <TopicChip key={topic} topic={topic} />
        ))}
        <span className="ml-auto">
          <OutcomeBadge outcome={vote.outcome} />
        </span>
      </div>
      <h4 className="text-sm font-semibold leading-snug">{vote.short_title}</h4>
      <Hemicycle parties={vote.parties} className="mx-auto max-w-72" />
      <VoteTotalsLine vote={vote} />
      <PartyKey vote={vote} />
    </button>
  );
}

export default VoteCard;
