import { isUnaffiliated } from '@/lib/daily/hemicycle';
import { sortBySeating } from '@/lib/daily/seating-order';
import type {
  DigestVote,
  DigestVoteParty,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ArrowUpRightIcon } from 'lucide-react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

type Majority = 'yes' | 'no' | 'abstain';

/** How most of a Fraktion's present members voted; null if nobody voted. */
export function majority(party: DigestVoteParty): Majority | null {
  const counts: [Majority, number][] = [
    ['yes', party.yes],
    ['no', party.no],
    ['abstain', party.abstain],
  ];
  const [label, count] = counts.reduce((best, c) =>
    c[1] > best[1] ? c : best,
  );
  return count > 0 ? label : null;
}

const MAJORITY_LABEL: Record<Majority, string> = {
  yes: 'Ja',
  no: 'Nein',
  abstain: 'Enthalten',
};

const MAJORITY_CLASS: Record<Majority, string> = {
  yes: 'text-[var(--daily-yes)]',
  no: 'text-[var(--daily-no)]',
  abstain: MUTED_TEXT,
};

/**
 * "So haben die Fraktionen gestimmt": two columns of Fraktion and majority.
 * Each row opens how that Fraktion's members voted, the same as tapping its
 * block in the chart.
 */
export function PartyVoteTable({
  vote,
  selected,
  onSelect,
  breakdownId,
}: {
  vote: DigestVote;
  selected: string | null;
  onSelect: (partyId: string) => void;
  /** The breakdown panel the rows open. */
  breakdownId: string;
}) {
  return (
    <ul className="grid grid-cols-2 gap-x-8">
      {sortBySeating(vote.parties)
        .filter((party) => !isUnaffiliated(party.party_id))
        .map((party) => {
          const verdict = majority(party);
          const active = selected === party.party_id;
          return (
            <li key={party.party_id}>
              <button
                type="button"
                aria-expanded={active}
                aria-controls={breakdownId}
                onClick={() => onSelect(party.party_id)}
                className={cn(
                  FOCUS_RING,
                  'flex w-full items-center justify-between gap-2 border-b py-3 text-left text-[15px]',
                  active
                    ? 'border-[var(--daily-ink)] font-semibold'
                    : 'border-[var(--daily-border)]',
                )}
              >
                <span className="truncate">{party.name}</span>
                <span
                  className={cn(
                    'font-semibold',
                    verdict && MAJORITY_CLASS[verdict],
                  )}
                >
                  {verdict ? MAJORITY_LABEL[verdict] : '–'}
                </span>
              </button>
            </li>
          );
        })}
    </ul>
  );
}

export function SourceLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        FOCUS_RING,
        'inline-flex min-h-10 items-center gap-1 rounded-md text-[15px] underline underline-offset-4',
        MUTED_TEXT,
      )}
    >
      {children}
      <ArrowUpRightIcon className="size-4" aria-hidden />
    </a>
  );
}
