import { Button } from '@/components/ui/button';
import { partyLabel } from '@/lib/stimmts/labels';
import { scorePuzzle } from '@/lib/stimmts/score';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import OutcomeLine from './outcome-line';
import PartyTile from './party-tile';
import { Verdict, VotePill } from './vote-pill';
import YesMeans from './yes-means';

type Props = {
  puzzle: Puzzle;
  /** Empty for a day the player missed: then only the real votes show. */
  guesses: Guesses;
  revealed: ReadonlySet<string>;
  onReveal?: (partyId: string) => void;
  onRevealAll?: () => void;
  /** Absent when looking back at a past day, which has no result to go to. */
  onShowResult?: () => void;
};

/**
 * Under the chamber during the reveal: what "Ja" meant, then, once every
 * party is turned over, what the Bundestag decided, and "Deine Tipps", the
 * player's tip beside the real vote for each party.
 */
function Reveal({
  puzzle,
  guesses,
  revealed,
  onReveal,
  onRevealAll,
  onShowResult,
}: Props) {
  const score = scorePuzzle(puzzle, guesses);
  const allRevealed = revealed.size === puzzle.parties.length;
  const played = Object.keys(guesses).length > 0;

  return (
    <div className="flex flex-col gap-4">
      <YesMeans yesMeans={puzzle.yesMeans} />
      {allRevealed && <OutcomeLine puzzle={puzzle} />}

      <section aria-labelledby="deine-tipps" className="flex flex-col gap-2">
        <h2 id="deine-tipps" className="mt-2 text-lg font-bold">
          {played ? 'Deine Tipps' : 'So wurde abgestimmt'}
        </h2>
        {!allRevealed && (
          <p className="text-sm text-muted-foreground">
            Tippe auf ein Logo im Halbkreis oder auf „Aufdecken“.
          </p>
        )}
        <ul className="flex flex-col gap-2">
          {score.parties.map((entry, index) => {
            const votes = puzzle.parties[index];
            const isRevealed = revealed.has(entry.partyId);
            return (
              <li
                key={entry.partyId}
                className="grid grid-cols-[auto_1fr_auto] items-start gap-3 rounded-lg border bg-card p-3"
              >
                <PartyTile partyId={entry.partyId} size="sm" />
                <div className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-semibold">
                    {partyLabel(entry.partyId)}
                  </span>
                  <div className="mt-0.5 flex flex-wrap gap-x-4 gap-y-1">
                    {played && (
                      <span className="flex flex-col gap-0.5">
                        <span className="text-xs text-muted-foreground">
                          Dein Tipp
                        </span>
                        <VotePill vote={entry.guess} kind="tip" />
                      </span>
                    )}
                    <span className="flex flex-col gap-0.5">
                      <span className="text-xs text-muted-foreground">
                        Abgestimmt
                      </span>
                      <VotePill
                        vote={isRevealed ? entry.actual : null}
                        kind="vote"
                      />
                    </span>
                  </div>
                  {isRevealed && (
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {votes.yes} Ja · {votes.no} Nein · {votes.abstain}{' '}
                      Enthaltung · {votes.noShow} nicht abgestimmt
                    </p>
                  )}
                </div>
                <div className="mt-0.5">
                  {isRevealed ? (
                    played && <Verdict correct={entry.correct} />
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onReveal?.(entry.partyId)}
                    >
                      Aufdecken
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
        {!allRevealed && (
          <Button variant="ghost" onClick={onRevealAll}>
            Alle aufdecken
          </Button>
        )}
      </section>

      {allRevealed && onShowResult && (
        <Button size="lg" className="w-full" onClick={onShowResult}>
          {played ? 'Zum Ergebnis' : 'Zurück zum Ergebnis'}
        </Button>
      )}
    </div>
  );
}

export default Reveal;
