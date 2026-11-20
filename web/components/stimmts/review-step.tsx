import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import PillButton from './pill-button';
import TipRow from './tip-row';

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
  onEdit: (partyId: string) => void;
  onReveal: () => void;
};

/**
 * Every party has a tip, and nothing is final yet: the last look at all five
 * before "Auflösen", the only step that ends the game.
 */
function ReviewStep({ puzzle, guesses, onEdit, onReveal }: Props) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-[var(--daily-border)] bg-[var(--daily-canvas)] p-4">
      {/* The page's own heading already says it to screen readers, and the
          focus lands there when the review opens. */}
      <p aria-hidden className="text-xl font-semibold">
        Deine Tipps
      </p>
      <TipRow
        puzzle={puzzle}
        guesses={guesses}
        current={null}
        onEdit={onEdit}
      />
      <p className="text-sm text-[var(--daily-muted)]">
        Tippe auf eine Partei, um den Tipp zu ändern.
      </p>
      <PillButton onClick={onReveal}>Auflösen</PillButton>
    </div>
  );
}

export default ReviewStep;
