import type { Progress } from './progress';

/** Asked once, after this many finished puzzles: enough to judge the game. */
export const FEEDBACK_AFTER_GAMES = 5;

/**
 * The optional Fillout form offered after a rating, for players who want to
 * say more. Empty until the form exists, which leaves the stars alone. It may
 * only ask about the game, never about a player's political views
 * (special-category data).
 */
export const STIMMTS_FEEDBACK_FORM_ID = '';

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
