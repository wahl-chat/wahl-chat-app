import { describe, expect, it } from 'bun:test';
import type { DayRecord } from './period';
import { streakOf } from './streak';

/** Day records from a pattern: P for a played day, x for a missed one. */
function days(pattern: string): DayRecord[] {
  return [...pattern].map((mark, index) =>
    mark === 'P'
      ? {
          kind: 'played',
          number: index + 1,
          playDate: '2026-11-01',
          topic: 'Energie',
          score: 3,
        }
      : { kind: 'missed', number: index + 1, playDate: '2026-11-01' },
  );
}

describe('streakOf', () => {
  it('is zero before anything was played', () => {
    expect(streakOf([], 1)).toEqual({ current: 0, best: 0 });
    expect(streakOf(days('x'), 1)).toEqual({ current: 0, best: 0 });
  });

  it('counts the days played in a row up to today', () => {
    expect(streakOf(days('PPP'), 3)).toEqual({ current: 3, best: 3 });
  });

  it('stays alive while today is still open', () => {
    // Days 1 and 2 played, day 3 (today) not yet.
    expect(streakOf(days('PPx'), 3)).toEqual({ current: 2, best: 2 });
  });

  it('breaks after a missed day but remembers the best run', () => {
    expect(streakOf(days('PPPxP'), 5)).toEqual({ current: 1, best: 3 });
    expect(streakOf(days('PPPxx'), 5)).toEqual({ current: 0, best: 3 });
  });

  it('counts days played, not days won', () => {
    const lowScores = days('PP').map((record) => ({ ...record, score: 0 }));
    expect(streakOf(lowScores, 2)).toEqual({ current: 2, best: 2 });
  });
});
