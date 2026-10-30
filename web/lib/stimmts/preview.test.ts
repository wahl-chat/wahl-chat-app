import { describe, expect, it } from 'bun:test';
import { berlinDate } from './berlin-time';
import { isPreviewEnabled, resolveClock } from './preview';

describe('isPreviewEnabled', () => {
  it('is on while developing and on a flagged test deployment', () => {
    expect(isPreviewEnabled({ nodeEnv: 'development' })).toBe(true);
    expect(
      isPreviewEnabled({
        vercelEnv: 'preview',
        nodeEnv: 'production',
        flag: 'true',
      }),
    ).toBe(true);
  });

  it('is off on a deployment without the flag', () => {
    expect(
      isPreviewEnabled({ vercelEnv: 'preview', nodeEnv: 'production' }),
    ).toBe(false);
  });

  it('is never on in production, even with the flag set', () => {
    expect(
      isPreviewEnabled({
        vercelEnv: 'production',
        nodeEnv: 'production',
        flag: 'true',
      }),
    ).toBe(false);
  });
});

describe('resolveClock', () => {
  const realNow = new Date('2026-10-03T09:00:00Z');

  const clock = (search: string, previewEnabled = true, now = realNow) =>
    resolveClock({
      previewEnabled,
      search,
      launchDate: '2026-11-01',
      puzzleCount: 30,
      now,
    });

  it('uses the real clock when preview is off', () => {
    // Even if someone adds ?day=2 to the address.
    expect(clock('?day=2', false)).toEqual({ now: realNow });
  });

  it('jumps to the requested day after the launch date in preview mode', () => {
    expect(berlinDate(clock('?day=1').now)).toBe('2026-11-01');
    expect(berlinDate(clock('?day=3').now)).toBe('2026-11-03');
  });

  it('goes no further than the day after the last puzzle', () => {
    expect(berlinDate(clock('?day=31').now)).toBe('2026-12-01');
    expect(berlinDate(clock('?day=99999999999999').now)).toBe('2026-12-01');
  });

  it('shows day 1 before the launch date when no day is given', () => {
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
