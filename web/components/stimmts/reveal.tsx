import { Button } from '@/components/ui/button';
import { OUTCOME_LABELS } from '@/lib/stimmts/labels';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { ArrowLeft, ArrowRight } from 'lucide-react';
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
  /** Absent when looking back at a past day, which has no result to go to. */
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
  onShowResult,
}: Props) {
  const allRevealed = revealed.size === puzzle.parties.length;
  const played = Object.keys(guesses).length > 0;

  return (
    <div className="flex flex-col gap-4">
      <YesMeans yesMeans={puzzle.yesMeans} />
      {allRevealed && (
        // On screen, the chamber's centre already says it.
        <p className="sr-only">
          Der Bundestag hat {OUTCOME_LABELS[puzzle.outcome]}.
        </p>
      )}

      <section aria-labelledby="deine-tipps" className="flex flex-col gap-2">
        <h2 id="deine-tipps" className="mt-2 text-lg font-bold">
          {played ? 'Deine Tipps' : 'So wurde abgestimmt'}
        </h2>
        {!allRevealed && (
          <p className="text-sm text-muted-foreground">
            Tippe auf eine Partei, um sie aufzudecken.
          </p>
        )}
        <RevealList
          puzzle={puzzle}
          guesses={guesses}
          revealed={revealed}
          open={open}
          onSelect={onSelect}
        />
        {!allRevealed && onRevealAll && (
          <Button variant="ghost" onClick={onRevealAll} className="self-center">
            Alle aufdecken
          </Button>
        )}
      </section>

      {allRevealed && onShowResult && (
        <PillButton onClick={onShowResult} className="mt-2">
          {played ? (
            <>
              Zum Ergebnis
              <ArrowRight aria-hidden strokeWidth={2.25} />
            </>
          ) : (
            <>
              <ArrowLeft aria-hidden strokeWidth={2.25} />
              Zurück zum Ergebnis
            </>
          )}
        </PillButton>
      )}
    </div>
  );
}

export default Reveal;
