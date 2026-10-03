import { Button } from '@/components/ui/button';
import { BASE_URL } from '@/lib/seo';
import {
  ANSWER_LABELS,
  OUTCOME_LABELS,
  partyLabel,
} from '@/lib/stimmts/labels';
import { scorePuzzle } from '@/lib/stimmts/score';
import { buildShareText } from '@/lib/stimmts/share';
import { activeStreak } from '@/lib/stimmts/streak';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useState } from 'react';
import Countdown from './countdown';
import ShareButton from './share-button';

const dayCount = (days: number) => `${days} ${days === 1 ? 'Tag' : 'Tage'}`;

type Props = {
  number: number;
  puzzle: Puzzle;
  guesses: Guesses;
  today: string;
  /** True when the game was already finished before the page opened. */
  startRevealed: boolean;
};

function Reveal({ number, puzzle, guesses, today, startRevealed }: Props) {
  const score = scorePuzzle(puzzle, guesses);
  const streak = useProgress((state) =>
    activeStreak(state.progress.streak, today),
  );
  const bestStreak = useProgress((state) => state.progress.streak.best);

  const [revealed, setRevealed] = useState<Set<string>>(
    () =>
      new Set(
        startRevealed ? puzzle.parties.map((party) => party.partyId) : [],
      ),
  );
  const allRevealed = revealed.size === puzzle.parties.length;

  const reveal = (partyId: string) =>
    setRevealed((previous) => new Set(previous).add(partyId));
  const revealAll = () =>
    setRevealed(new Set(puzzle.parties.map((party) => party.partyId)));

  return (
    <section className="flex flex-col gap-4">
      <p className="text-sm font-medium">{puzzle.yesMeans}</p>

      <ul className="flex flex-col gap-3">
        {score.parties.map((entry, index) => {
          const votes = puzzle.parties[index];
          const isRevealed = revealed.has(entry.partyId);
          return (
            <li key={entry.partyId} className="rounded-lg border p-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-semibold">{partyLabel(entry.partyId)}</h2>
                {isRevealed ? (
                  <span
                    className={
                      entry.correct
                        ? 'text-sm font-medium text-green-600'
                        : 'text-sm font-medium text-red-600'
                    }
                  >
                    {entry.correct ? '✓ Richtig' : '✗ Falsch'}
                  </span>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => reveal(entry.partyId)}
                  >
                    Aufdecken
                  </Button>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                Dein Tipp: {entry.guess ? ANSWER_LABELS[entry.guess] : '–'}
              </p>
              {isRevealed && (
                <>
                  <p className="mt-1 font-medium">
                    Tatsächlich: {ANSWER_LABELS[entry.actual]}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {votes.yes} Ja · {votes.no} Nein · {votes.abstain}{' '}
                    Enthaltung · {votes.noShow} nicht abgestimmt
                  </p>
                </>
              )}
            </li>
          );
        })}
      </ul>

      {!allRevealed && (
        <Button variant="ghost" onClick={revealAll}>
          Alle aufdecken
        </Button>
      )}

      {allRevealed && (
        <div className="flex flex-col gap-2 rounded-lg bg-muted p-4">
          <p className="text-lg font-semibold">
            {score.correct} von {score.total} richtig
          </p>
          <p>Der Antrag wurde {OUTCOME_LABELS[puzzle.outcome]}.</p>
          <p className="text-sm text-muted-foreground">
            Serie: {dayCount(streak)} · Rekord: {dayCount(bestStreak)}
          </p>
          <ShareButton
            text={buildShareText({
              puzzleNumber: number,
              score,
              url: `${BASE_URL}/stimmts`,
            })}
          />
          <Countdown />
          <a
            className="text-sm underline"
            href={puzzle.source.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Quelle: {puzzle.source.label}
          </a>
        </div>
      )}
    </section>
  );
}

export default Reveal;
