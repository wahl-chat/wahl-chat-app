import { isUnaffiliated } from '@/lib/daily/hemicycle';
import { sortBySeating } from '@/lib/daily/seating-order';
import type {
  DigestVote,
  DigestVoteParty,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ArrowUpRightIcon } from 'lucide-react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

type Majority = 'Ja' | 'Nein' | 'Enthalten';

/** How most of a Fraktion's present members voted; null if nobody voted. */
export function majority(party: DigestVoteParty): Majority | null {
  const counts: [Majority, number][] = [
    ['Ja', party.yes],
    ['Nein', party.no],
    ['Enthalten', party.abstain],
  ];
  const [label, count] = counts.reduce((best, c) =>
    c[1] > best[1] ? c : best,
  );
  return count > 0 ? label : null;
}

const MAJORITY_CLASS: Record<Majority, string> = {
  Ja: 'text-[var(--daily-yes)]',
  Nein: 'text-[var(--daily-no)]',
  Enthalten: MUTED_TEXT,
};

/** "So haben die Fraktionen gestimmt": two columns of Fraktion and majority. */
export function PartyVoteTable({ vote }: { vote: DigestVote }) {
  return (
    <dl className="grid grid-cols-2 gap-x-8">
      {sortBySeating(vote.parties)
        .filter((party) => !isUnaffiliated(party.party_id))
        .map((party) => {
          const verdict = majority(party);
          return (
            <div
              key={party.party_id}
              className="flex items-center justify-between gap-2 border-b border-[var(--daily-border)] py-3 text-[15px]"
            >
              <dt className="truncate">{party.name}</dt>
              <dd
                className={cn(
                  'font-semibold',
                  verdict && MAJORITY_CLASS[verdict],
                )}
              >
                {verdict ?? '–'}
              </dd>
            </div>
          );
        })}
    </dl>
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
