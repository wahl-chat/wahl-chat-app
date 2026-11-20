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
    <section
      aria-labelledby="review-tips"
      className="flex flex-col gap-4 rounded-lg border border-[var(--daily-border)] bg-[var(--daily-canvas)] p-4"
    >
      <h2 id="review-tips" className="text-xl font-semibold">
        Deine Tipps
      </h2>
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
    </section>
  );
}

export default ReviewStep;
