import { describe, expect, it } from 'bun:test';
import { berlinDate } from './berlin-time';
import { resolveClock } from './preview';
import type { Schedule } from './types';

const schedule: Schedule = {
  startDate: '2026-11-01',
  puzzleIds: ['a', 'b', 'c'],
};
const realNow = new Date('2026-10-03T09:00:00Z');

const clock = (search: string, previewEnabled = true, now = realNow) =>
  resolveClock({ previewEnabled, search, schedule, now });

describe('resolveClock', () => {
  it('uses the real clock when preview is off', () => {
    // Even if someone adds ?day=2 to the address.
    expect(clock('?day=2', false)).toEqual({ now: realNow });
  });

  it('jumps to the requested day of the schedule in preview mode', () => {
    expect(berlinDate(clock('?day=1').now)).toBe('2026-11-01');
    expect(berlinDate(clock('?day=3').now)).toBe('2026-11-03');
  });

  it('shows day 1 before the start date when no day is given', () => {
    expect(berlinDate(clock('').now)).toBe('2026-11-01');
  });

  it('follows the real date once the game has started', () => {
    const afterStart = new Date('2026-11-04T10:00:00Z');
    expect(berlinDate(clock('', true, afterStart).now)).toBe('2026-11-04');
  });

  it('ignores a day that is not a positive whole number', () => {
    for (const search of [
      '?day=0',
      '?day=-2',
      '?day=abc',
      '?day=1.5',
      '?day=',
    ]) {
      expect(berlinDate(clock(search).now)).toBe('2026-11-01');
    }
  });
});
