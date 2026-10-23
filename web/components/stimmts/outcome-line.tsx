import { voteTotals } from '@/lib/stimmts/game-view';
import { OUTCOME_LABELS } from '@/lib/stimmts/labels';
import type { Puzzle } from '@/lib/stimmts/types';

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
