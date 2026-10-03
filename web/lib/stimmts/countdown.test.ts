import { describe, expect, it } from 'bun:test';
import { formatCountdown } from './countdown';

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
