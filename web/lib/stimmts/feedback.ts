import type { Progress } from './progress';

/** Asked once, after this many finished puzzles: enough to judge the game. */
export const FEEDBACK_AFTER_GAMES = 5;

/**
 * The Fillout form that asks how players like the game. Empty until the form
 * exists, which keeps the prompt hidden. It may only ask about the game,
 * never about a player's political views (special-category data).
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
  formId = STIMMTS_FEEDBACK_FORM_ID,
): boolean {
  return (
    formId !== '' &&
    !alreadyAsked &&
    finishedGameCount(progress) >= FEEDBACK_AFTER_GAMES
  );
}
