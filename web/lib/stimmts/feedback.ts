import type { Progress } from './progress';
import type { StorageLike } from './progress-store';

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

// Not the key of the earlier star rating, so a player who was asked that is
// still asked this.
const ASKED_KEY = 'stimmts:more-games-asked';

// Without storage this flag still keeps the question from returning in the
// same visit; only a reload may ask once more.
let askedThisSession = false;

export function wasAsked(storage: StorageLike | null): boolean {
  if (askedThisSession) {
    return true;
  }
  try {
    return storage?.getItem(ASKED_KEY) === '1';
  } catch {
    return false;
  }
}

export function markAsked(storage: StorageLike | null): void {
  askedThisSession = true;
  try {
    storage?.setItem(ASKED_KEY, '1');
  } catch {
    // Nothing to remember it in beyond this visit.
  }
}

/**
 * Only a study status known to be off lets the card show: "not known yet"
 * could still turn out to be on, and while the study runs its questionnaire is
 * the only ask. The fly-in visit belongs to the game's result, so the question
 * waits for the next one. The question is about the game, so it needs the
 * game to be on: a switched-off game has no players to ask, and a status not
 * yet known is treated as off rather than risk asking about something hidden.
 */
export function shouldShowFeedCard(input: {
  progress: Progress;
  asked: boolean;
  studyRunning: boolean | null;
  flyingIn: boolean;
  gameOn: boolean | null;
}): boolean {
  return (
    input.gameOn === true &&
    input.studyRunning === false &&
    !input.flyingIn &&
    shouldAskForFeedback(input.progress, input.asked)
  );
}
