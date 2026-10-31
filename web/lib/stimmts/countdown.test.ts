import { describe, expect, it } from 'bun:test';
import { countdownTarget, formatCountdown } from './countdown';

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;

describe('formatCountdown', () => {
  it('formats hours, minutes and seconds with leading zeros', () => {
    expect(formatCountdown(5 * HOUR + 3 * MINUTE + 9 * SECOND)).toBe(
      '05:03:09',
    );
    expect(formatCountdown(59 * SECOND)).toBe('00:00:59');
    expect(formatCountdown(HOUR)).toBe('01:00:00');
  });

  it('rounds up, so the final second still shows', () => {
    expect(formatCountdown(1)).toBe('00:00:01');
    expect(formatCountdown(999)).toBe('00:00:01');
    expect(formatCountdown(1001)).toBe('00:00:02');
  });

  it('stops at zero instead of going negative', () => {
    expect(formatCountdown(0)).toBe('00:00:00');
    expect(formatCountdown(-5 * SECOND)).toBe('00:00:00');
  });

  it('copes with the 25-hour day', () => {
    expect(formatCountdown(25 * HOUR)).toBe('25:00:00');
  });
});

describe('countdownTarget', () => {
  // 23:59:59 and 00:00:01 in Berlin on the night of 23/24 October 2026, still
  // summer time (UTC+2): the clocks change on 25 October.
  const beforeMidnight = new Date('2026-10-23T21:59:59Z');
  const afterMidnight = new Date('2026-10-23T22:00:01Z');

  it('counts to the next Berlin midnight', () => {
    const target = countdownTarget(beforeMidnight, null);
    expect(new Date(target).toISOString()).toBe('2026-10-23T22:00:00.000Z');
    expect(countdownTarget(beforeMidnight, target)).toBe(target);
  });

  it('moves on to the following midnight once the target has passed', () => {
    const passed = countdownTarget(beforeMidnight, null);
    const next = countdownTarget(afterMidnight, passed);
    // The night of the clock change, so this Berlin day is 25 hours long.
    expect(new Date(next).toISOString()).toBe('2026-10-24T22:00:00.000Z');
    expect(formatCountdown(next - afterMidnight.getTime())).not.toBe(
      '00:00:00',
    );
  });
});
