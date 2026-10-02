import { describe, expect, it } from 'bun:test';
import {
  EMPTY_STREAK,
  type StreakState,
  activeStreak,
  recordPlay,
} from './streak';

describe('recordPlay', () => {
  it('starts a streak with the first puzzle', () => {
    expect(recordPlay(EMPTY_STREAK, '2026-10-15')).toEqual({
      current: 1,
      best: 1,
      lastPlayed: '2026-10-15',
    });
  });

  it('extends the streak on consecutive days', () => {
    let state = recordPlay(EMPTY_STREAK, '2026-10-15');
    state = recordPlay(state, '2026-10-16');
    state = recordPlay(state, '2026-10-17');
    expect(state).toEqual({ current: 3, best: 3, lastPlayed: '2026-10-17' });
  });

  it('counts a day only once, however often the puzzle is finished', () => {
    const once = recordPlay(EMPTY_STREAK, '2026-10-15');
    expect(recordPlay(once, '2026-10-15')).toBe(once);
  });

  it('restarts after a missed day but remembers the best run', () => {
    let state = recordPlay(EMPTY_STREAK, '2026-10-15');
    state = recordPlay(state, '2026-10-16');
    state = recordPlay(state, '2026-10-18'); // 17th skipped
    expect(state).toEqual({ current: 1, best: 2, lastPlayed: '2026-10-18' });
  });

  it('continues across month and year boundaries', () => {
    let state = recordPlay(EMPTY_STREAK, '2026-12-31');
    state = recordPlay(state, '2027-01-01');
    expect(state.current).toBe(2);
  });
});

describe('activeStreak', () => {
  const state: StreakState = {
    current: 4,
    best: 6,
    lastPlayed: '2026-10-15',
  };

  it('shows the streak on the day it was played and the day after', () => {
    expect(activeStreak(state, '2026-10-15')).toBe(4);
    expect(activeStreak(state, '2026-10-16')).toBe(4);
  });

  it('shows zero once a whole day has been missed', () => {
    expect(activeStreak(state, '2026-10-17')).toBe(0);
  });

  it('shows zero for a player who never played', () => {
    expect(activeStreak(EMPTY_STREAK, '2026-10-15')).toBe(0);
  });
});
