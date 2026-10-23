import { BASE_URL } from '@/lib/seo';
import { PUZZLES, SCHEDULE } from '@/lib/stimmts/content';
import { dayRecords } from '@/lib/stimmts/period';
import { scorePuzzle } from '@/lib/stimmts/score';
import { buildShareText } from '@/lib/stimmts/share';
import { streakOf } from '@/lib/stimmts/streak';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useMemo } from 'react';
import Countdown from './countdown';
import OutcomeLine from './outcome-line';
import ShareButton from './share-button';

const dayCount = (days: number) => `${days} ${days === 1 ? 'Tag' : 'Tage'}`;

type Props = {
  number: number;
  puzzle: Puzzle;
  guesses: Guesses;
  onReview: () => void;
};

/** The end of the day's puzzle: the score, the streak, sharing, the countdown. */
function Result({ number, puzzle, guesses, onReview }: Props) {
  const score = scorePuzzle(puzzle, guesses);
  const progress = useProgress((state) => state.progress);
  const streak = useMemo(
    () =>
      streakOf(
        dayRecords({
          schedule: SCHEDULE,
          puzzles: PUZZLES,
          progress,
          throughNumber: number,
        }),
        number,
      ),
    [progress, number],
  );

  return (
    <section aria-live="polite" className="flex flex-col gap-4">
      <p className="text-lg font-semibold">
        {score.correct} von {score.total} richtig
      </p>
      <OutcomeLine puzzle={puzzle} />
      <p className="text-sm text-muted-foreground">
        Serie: {dayCount(streak.current)} · Rekord: {dayCount(streak.best)}
      </p>
      <ShareButton
        text={buildShareText({
          puzzleNumber: number,
          score,
          url: `${BASE_URL}/stimmts`,
        })}
      />
      <Countdown />
      <p className="text-center text-sm">
        <button
          type="button"
          onClick={onReview}
          className="underline underline-offset-[3px]"
        >
          Abstimmung ansehen
        </button>
        {' · '}
        <a
          className="underline underline-offset-[3px]"
          href={puzzle.source.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Quelle: {puzzle.source.label}
        </a>
      </p>
    </section>
  );
}

export default Result;
