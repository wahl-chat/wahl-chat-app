import type { Progress } from './progress';

/**
 * Asked once, after this many finished puzzles. The question is whether the
 * format is worth more games, which a player can answer after one round.
 */
export const FEEDBACK_AFTER_GAMES = 1;

export function finishedGameCount(progress: Progress): number {
  return Object.values(progress.games).filter(
    (game) => game.finishedOn !== null,
  ).length;
}

export function shouldAskForFeedback(
  progress: Progress,
  alreadyAsked: boolean,
): boolean {
  return !alreadyAsked && finishedGameCount(progress) >= FEEDBACK_AFTER_GAMES;
}
