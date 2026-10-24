import { ANSWER_LABELS, partyLabel } from '@/lib/stimmts/labels';
import { scorePuzzle } from '@/lib/stimmts/score';
import type {
  Guesses,
  PartyResult,
  Puzzle,
  VoteAnswer,
} from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import PartyTile from './party-tile';
import VoteDot, { type DotKind } from './vote-dot';

// Played back on every reveal; with reduced motion the vote just appears.
const FLIP = 'animate-stimmts-flip motion-reduce:animate-none';

type Props = {
  puzzle: Puzzle;
  /** Empty for a vote looked at without tips: then only real votes show. */
  guesses: Guesses;
  revealed: ReadonlySet<string>;
  /** The party whose counts are open, if any. */
  open: string | null;
  onSelect: (partyId: string) => void;
};

/**
 * "Deine Tipps": one line per party, the player's tip beside the real vote
 * and the verdict. Each line is one button: the first tap turns the party
 * over and opens its exact counts, later taps open and close them. The
 * party's logo names it; its name is read out by the button's label.
 */
function RevealList({ puzzle, guesses, revealed, open, onSelect }: Props) {
  const score = scorePuzzle(puzzle, guesses);
  const played = Object.keys(guesses).length > 0;

  return (
    <ul className="border-t">
      {score.parties.map((entry, index) => {
        const party = puzzle.parties[index];
        const shown = revealed.has(entry.partyId);
        const isOpen = shown && open === entry.partyId;
        const panelId = `stimmts-counts-${entry.partyId}`;
        const label = [
          partyLabel(entry.partyId),
          played && entry.guess && `dein Tipp ${ANSWER_LABELS[entry.guess]}`,
          shown
            ? [
                `abgestimmt ${ANSWER_LABELS[entry.actual]}`,
                played && (entry.correct ? 'richtig' : 'falsch'),
              ]
                .filter(Boolean)
                .join(', ')
            : 'aufdecken',
        ]
          .filter(Boolean)
          .join(', ');

        return (
          <li key={entry.partyId} className="border-b">
            <button
              type="button"
              onClick={() => onSelect(entry.partyId)}
              aria-label={label}
              {...(shown
                ? { 'aria-expanded': isOpen, 'aria-controls': panelId }
                : {})}
              className={cn(
                'grid min-h-14 w-full items-center gap-3 px-1 py-2 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                played
                  ? 'grid-cols-[auto_1fr_16px_1fr_24px_16px]'
                  : 'grid-cols-[auto_1fr_16px]',
              )}
            >
              <PartyTile partyId={entry.partyId} size="sm" />
              {played && (
                <>
                  <VoteMark vote={entry.guess} tip />
                  <span
                    aria-hidden
                    className="text-center text-[13px] text-muted-foreground"
                  >
                    →
                  </span>
                </>
              )}
              <span className="flex [perspective:400px]">
                {shown ? (
                  <span className={FLIP}>
                    <VoteMark vote={entry.actual} />
                  </span>
                ) : (
                  <span
                    aria-hidden
                    className="inline-flex h-[22px] min-w-11 items-center justify-center rounded-full border border-dashed border-muted-foreground text-[13px] font-semibold text-muted-foreground"
                  >
                    ?
                  </span>
                )}
              </span>
              {played && (
                <span className="flex justify-center">
                  {shown && (
                    <span
                      aria-hidden
                      className={cn(
                        'inline-flex size-6 items-center justify-center rounded-full text-[13px] font-bold text-background',
                        entry.correct ? 'bg-result-correct' : 'bg-result-wrong',
                        FLIP,
                      )}
                    >
                      {entry.correct ? '✓' : '✗'}
                    </span>
                  )}
                </span>
              )}
              {shown ? (
                <ChevronDown
                  aria-hidden
                  className={cn(
                    'size-4 justify-self-center text-muted-foreground transition-transform duration-200 motion-reduce:transition-none',
                    isOpen && 'rotate-180',
                  )}
                />
              ) : (
                <span />
              )}
            </button>
            {isOpen && (
              <div
                id={panelId}
                className="pb-4 pl-14 pr-1 duration-200 animate-in fade-in slide-in-from-top-1 motion-reduce:animate-none"
              >
                <Counts party={party} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** A vote with its dot: a ring for the player's tip, a fill for the real vote. */
function VoteMark({
  vote,
  tip = false,
}: { vote: VoteAnswer | null; tip?: boolean }) {
  if (!vote) {
    return <span className="text-sm text-muted-foreground">–</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm font-medium">
      <VoteDot kind={vote} ring={tip} />
      {ANSWER_LABELS[vote]}
    </span>
  );
}

const COUNT_PARTS: {
  kind: DotKind;
  label: string;
  bar: string;
  count: (party: PartyResult) => number;
}[] = [
  { kind: 'yes', label: 'Ja', bar: 'bg-seat-yes', count: (p) => p.yes },
  { kind: 'no', label: 'Nein', bar: 'bg-seat-no', count: (p) => p.no },
  {
    kind: 'abstain',
    label: 'Enthaltung',
    bar: 'bg-seat-abstain',
    count: (p) => p.abstain,
  },
  {
    kind: 'absent',
    label: 'Abwesend',
    bar: 'bg-seat-pending',
    count: (p) => p.noShow,
  },
];

/**
 * A party's exact counts: the split as a bar in the seat colours, then the
 * four numbers, zeros dimmed. Nothing more; the source is linked once, at
 * the foot of the result.
 */
function Counts({ party }: { party: PartyResult }) {
  return (
    <>
      <div
        aria-hidden
        className="flex h-2 gap-0.5 overflow-hidden rounded-full"
      >
        {COUNT_PARTS.filter((part) => part.count(party) > 0).map((part) => (
          <span
            key={part.kind}
            className={part.bar}
            style={{ flexGrow: part.count(party) }}
          />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-4 gap-1">
        {COUNT_PARTS.map((part) => {
          const count = part.count(party);
          return (
            <li
              key={part.kind}
              className={cn(
                'flex flex-col gap-0.5',
                count === 0 && 'opacity-45',
              )}
            >
              <span className="font-display text-xl font-extrabold tabular-nums leading-6">
                {count}
              </span>
              <span className="inline-flex items-center gap-1 whitespace-nowrap text-[11px] font-medium leading-[14px] text-muted-foreground">
                <VoteDot kind={part.kind} className="size-[7px]" />
                {part.label}
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export default RevealList;
