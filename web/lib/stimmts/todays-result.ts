import { PUZZLES } from './content';
import type { Progress } from './progress';
import { scorePuzzle } from './score';

export type TodaysResult = {
  correct: number;
  total: number;
  /** Right or wrong per party, in seating order. */
  verdicts: boolean[];
};

const BY_ID = new Map(PUZZLES.map((puzzle) => [puzzle.id, puzzle]));

/**
 * The score of the game this device finished on `today`, if any. It needs no
 * schedule, so the header can name the score before the switch is known: a
 * game can only be finished on the day it runs.
 */
export function todaysResult(
  progress: Progress,
  today: string,
): TodaysResult | null {
  for (const [id, game] of Object.entries(progress.games)) {
    const puzzle = BY_ID.get(id);
    if (game.finishedOn !== today || !puzzle) {
      continue;
    }
    const score = scorePuzzle(puzzle, game.guesses);
    return {
      correct: score.correct,
      total: score.total,
      verdicts: score.parties.map((party) => party.correct),
    };
  }
  return null;
}
