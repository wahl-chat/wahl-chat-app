import { allRevealed } from '@/lib/stimmts/game-view';
import { OUTCOME_LABELS } from '@/lib/stimmts/labels';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { ArrowLeft } from 'lucide-react';
import PillButton from './pill-button';
import RevealList from './reveal-list';
import YesMeans from './yes-means';

type Props = {
  puzzle: Puzzle;
  /** Empty for a vote looked at without tips: then only the real votes show. */
  guesses: Guesses;
  revealed: ReadonlySet<string>;
  /** The party whose counts are open under its row, if any. */
  open: string | null;
  /** A tap on a party's row (see selectParty). */
  onSelect: (partyId: string) => void;
  onRevealAll?: () => void;
  /** The parties are being turned over one after another. */
  revealing?: boolean;
  /**
   * Only for a vote looked at without tips: with tips, the result follows by
   * itself once the last party is turned over.
   */
  onShowResult?: () => void;
};

/**
 * Under the chamber during the reveal: what "Ja" meant, then "Deine Tipps",
 * the player's tip beside the real vote for each party.
 */
function Reveal({
  puzzle,
  guesses,
  revealed,
  open,
  onSelect,
  onRevealAll,
  revealing = false,
  onShowResult,
}: Props) {
  const complete = allRevealed(puzzle, revealed);
  const played = Object.keys(guesses).length > 0;

  return (
    <div className="flex flex-col gap-4">
      <YesMeans yesMeans={puzzle.yesMeans} />
      {/* On screen, the chamber's centre already says it. The region stays
          mounted so that filling it is announced, before the result follows. */}
      <p role="status" className="sr-only">
        {complete && `Der Bundestag hat ${OUTCOME_LABELS[puzzle.outcome]}.`}
      </p>

      <section aria-labelledby="deine-tipps" className="flex flex-col gap-2">
        <h2 id="deine-tipps" className="mt-2 text-lg font-bold">
          {played ? 'Deine Tipps' : 'So wurde abgestimmt'}
        </h2>
        {!complete && onRevealAll && (
          <>
            {/* Stays mounted while the sequence runs, so focus is not dropped. */}
            <PillButton
              aria-disabled={revealing}
              onClick={revealing ? undefined : onRevealAll}
              className={revealing ? 'opacity-50' : undefined}
            >
              Auflösen
            </PillButton>
            <p className="text-center text-sm text-muted-foreground">
              Oder tippe auf eine Partei.
            </p>
          </>
        )}
        <RevealList
          puzzle={puzzle}
          guesses={guesses}
          revealed={revealed}
          open={open}
          onSelect={onSelect}
        />
      </section>

      {complete && onShowResult && !played && (
        <PillButton onClick={onShowResult} className="mt-2">
          <ArrowLeft aria-hidden strokeWidth={2.25} />
          Zurück zum Ergebnis
        </PillButton>
      )}
    </div>
  );
}

export default Reveal;
