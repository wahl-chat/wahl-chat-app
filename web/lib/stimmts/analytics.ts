import { track } from '@vercel/analytics/react';
import { claimOnce } from './claim-once';
import { browserStorage } from './progress-store';

// Counts only. The tips themselves never leave the device: a player's tips
// are predictions, but a log of them per party could still be read as views.

/** Once per puzzle and browser: not again after a reload or in another tab. */
export function trackPuzzleStarted(day: number, puzzleId: string) {
  if (claimOnce(browserStorage(), `stimmts:started:${puzzleId}`)) {
    track('stimmts_puzzle_started', { day });
  }
}

export function trackPuzzleCompleted(day: number, score: number) {
  track('stimmts_puzzle_completed', { day, score });
}

export type MoreGamesAnswer = 'yes' | 'no' | 'dismissed';

/**
 * Whether players want more small games, asked once after the first finished
 * puzzle. A close without an answer is 'dismissed', so skips count too. The
 * placement tells answers given on the old result screen from the feed's.
 */
export function trackMoreGames(
  answer: MoreGamesAnswer,
  games: number,
  placement: 'feed',
) {
  track('stimmts_more_games', { answer, games, placement });
}

export type ShareMethod = 'share' | 'copy';

/** From a day's result, or from the closing screen after the last day. */
export function trackResultShared(
  screen: 'result' | 'closing',
  method: ShareMethod,
  day?: number,
) {
  track('stimmts_result_shared', { screen, method, day: day ?? null });
}
