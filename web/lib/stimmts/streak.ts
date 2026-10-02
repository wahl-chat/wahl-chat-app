import { addDays } from './berlin-time';

export type StreakState = {
  /** Consecutive days played, as of the last day played. */
  current: number;
  best: number;
  /** Berlin date (YYYY-MM-DD) of the last finished puzzle. */
  lastPlayed: string | null;
};

export const EMPTY_STREAK: StreakState = {
  current: 0,
  best: 0,
  lastPlayed: null,
};

/**
 * Counts a finished puzzle. The streak is days played, not days won, so a bad
 * score never breaks it; only skipping a whole day does.
 */
export function recordPlay(state: StreakState, today: string): StreakState {
  if (state.lastPlayed === today) {
    return state;
  }
  const continues = state.lastPlayed === addDays(today, -1);
  const current = continues ? state.current + 1 : 1;
  return {
    current,
    best: Math.max(state.best, current),
    lastPlayed: today,
  };
}

/**
 * The streak to show today. `current` is only updated when a puzzle is
 * finished, so after a missed day the stored value is out of date: the streak
 * is alive only if the player finished a puzzle today or yesterday.
 */
export function activeStreak(state: StreakState, today: string): number {
  const alive =
    state.lastPlayed === today || state.lastPlayed === addDays(today, -1);
  return alive ? state.current : 0;
}
