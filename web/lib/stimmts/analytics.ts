import { track } from '@vercel/analytics/react';

// Counts only. The tips themselves never leave the device: a player's tips
// are predictions, but a log of them per party could still be read as views.

export function trackPuzzleStarted(day: number) {
  track('stimmts_puzzle_started', { day });
}

export function trackPuzzleCompleted(day: number, score: number) {
  track('stimmts_puzzle_completed', { day, score });
}

/** The one-tap rating, 1 to 5 stars, after the fifth finished puzzle. */
export function trackRated(stars: number, games: number) {
  track('stimmts_rated', { stars, games });
}

/** Closing the rating card without a rating, so skips can be counted too. */
export function trackRatingDismissed(games: number) {
  track('stimmts_rating_dismissed', { games });
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
