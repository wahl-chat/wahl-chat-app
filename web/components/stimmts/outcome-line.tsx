import { voteTotals } from '@/lib/stimmts/game-view';
import { OUTCOME_LABELS } from '@/lib/stimmts/labels';
import type { Puzzle } from '@/lib/stimmts/types';
import { ArrowUpRight, ChevronRight } from 'lucide-react';
import Image from 'next/image';

/**
 * What the Bundestag decided, in one plain line. It is what the Bundestag
 * did; how the player did lives under "Deine Tipps" and "Dein Ergebnis".
 */
function OutcomeLine({ puzzle }: { puzzle: Puzzle }) {
  const totals = voteTotals(puzzle);
  return (
    <p className="flex items-baseline justify-between gap-3 border-y py-3 text-[15px] leading-[22px]">
      <span className="font-semibold">
        Der Bundestag hat {OUTCOME_LABELS[puzzle.outcome]}
      </span>
      <span className="font-mono tabular-nums text-muted-foreground">
        <span className="sr-only">
          {totals.yes} Ja zu {totals.no} Nein
        </span>
        <span aria-hidden>
          {totals.yes} : {totals.no}
        </span>
      </span>
    </p>
  );
}

export default OutcomeLine;

/**
 * The outcome on the result screen, as a card that opens the vote itself:
 * the chamber with how every member voted, without the player's tips. The
 * bar is the vote's split, in the seat colours, beside its numbers. The
 * card's foot names where the vote's data comes from.
 */
export function OutcomeCard({
  puzzle,
  onOpen,
}: {
  puzzle: Puzzle;
  onOpen: () => void;
}) {
  const { yes, no } = voteTotals(puzzle);
  const abstain = puzzle.parties.reduce((sum, party) => sum + party.abstain, 0);
  const cast = Math.max(1, yes + no + abstain);
  const share = (count: number) => `${(count / cast) * 100}%`;
  const counts = [
    `${yes} Ja`,
    ...(abstain > 0 ? [`${abstain} Enthaltung`] : []),
    `${no} Nein`,
  ].join(' · ');

  return (
    // A link cannot sit inside a button, so the card holds the two side by
    // side: the vote above, the source below.
    <div className="overflow-hidden rounded-xl border bg-card">
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Der Bundestag hat ${OUTCOME_LABELS[puzzle.outcome]}, ${counts}. Abstimmung ansehen`}
        className="group flex w-full items-center gap-4 p-4 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span aria-hidden className="flex min-w-0 flex-1 flex-col gap-2">
          <span className="text-sm text-muted-foreground">
            Der Bundestag hat
          </span>
          <span className="font-display text-2xl font-extrabold leading-none tracking-[-0.01em]">
            {OUTCOME_LABELS[puzzle.outcome]}
          </span>
          <span className="mt-1 flex h-2 w-full overflow-hidden rounded-full bg-muted">
            <span className="bg-seat-yes" style={{ width: share(yes) }} />
            <span
              className="bg-seat-abstain"
              style={{ width: share(abstain) }}
            />
            <span className="bg-seat-no" style={{ width: share(no) }} />
          </span>
          <span className="text-xs tabular-nums text-muted-foreground">
            {counts}
          </span>
        </span>
        <ChevronRight
          aria-hidden
          className="size-5 flex-none text-muted-foreground transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none"
        />
      </button>
      <a
        href={puzzle.source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-between gap-3 border-t px-4 py-3 text-xs text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex items-center gap-2">
          Quelle
          {isAbgeordnetenwatch(puzzle.source.url) ? (
            <AbgeordnetenwatchLogo />
          ) : (
            <span className="font-medium text-foreground">
              {puzzle.source.label}
            </span>
          )}
        </span>
        <ArrowUpRight aria-hidden className="size-4 flex-none" />
      </a>
    </div>
  );
}

function isAbgeordnetenwatch(url: string): boolean {
  const { hostname } = new URL(url);
  return (
    hostname === 'abgeordnetenwatch.de' ||
    hostname.endsWith('.abgeordnetenwatch.de')
  );
}

/**
 * Abgeordnetenwatch's logo from its press kit. Its letters are cut out, so
 * the purple version reads on the light card and the white one on the dark.
 */
function AbgeordnetenwatchLogo() {
  return (
    <>
      <Image
        alt="Abgeordnetenwatch"
        width={56}
        height={32}
        src="/images/stimmts/abgeordnetenwatch.png"
        className="h-8 w-auto dark:hidden"
      />
      <Image
        alt="Abgeordnetenwatch"
        width={56}
        height={32}
        src="/images/stimmts/abgeordnetenwatch-dark.png"
        className="hidden h-8 w-auto dark:block"
      />
    </>
  );
}
