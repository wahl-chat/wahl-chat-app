import { describe, expect, it } from 'bun:test';
import {
  addDays,
  berlinDate,
  daysBetween,
  isIsoDate,
  nextPuzzleAt,
} from './berlin-time';

const at = (iso: string) => new Date(iso);

describe('berlinDate', () => {
  it('rolls over at midnight in summer time (UTC+2)', () => {
    expect(berlinDate(at('2026-10-14T21:59:59Z'))).toBe('2026-10-14');
    expect(berlinDate(at('2026-10-14T22:00:00Z'))).toBe('2026-10-15');
  });

  it('rolls over at midnight in winter time (UTC+1)', () => {
    expect(berlinDate(at('2026-12-31T22:59:59Z'))).toBe('2026-12-31');
    expect(berlinDate(at('2026-12-31T23:00:00Z'))).toBe('2027-01-01');
  });

  it('ignores the player: a late evening in New York is already tomorrow', () => {
    // 20:30 in New York (UTC-4) is 02:30 the next day in Berlin.
    expect(berlinDate(at('2026-10-15T00:30:00-04:00'))).toBe('2026-10-15');
    expect(berlinDate(at('2026-10-14T20:30:00-04:00'))).toBe('2026-10-15');
  });
});

describe('isIsoDate', () => {
  it('accepts real calendar dates', () => {
    expect(isIsoDate('2026-11-01')).toBe(true);
    expect(isIsoDate('2028-02-29')).toBe(true);
  });

  it('rejects impossible days, other formats and non-strings', () => {
    for (const value of [
      '2026-02-31',
      '2027-02-29',
      '2026-13-01',
      '2026-1-1',
      '01.11.2026',
      '2026-11-01T10:00:00Z',
      '',
      null,
      20261101,
    ]) {
      expect(isIsoDate(value)).toBe(false);
    }
  });
});

describe('daysBetween and addDays', () => {
  it('counts days across month, year and leap-day boundaries', () => {
    expect(daysBetween('2026-10-15', '2026-10-15')).toBe(0);
    expect(daysBetween('2026-10-15', '2026-11-14')).toBe(30);
    expect(daysBetween('2026-12-30', '2027-01-02')).toBe(3);
    expect(daysBetween('2028-02-28', '2028-03-01')).toBe(2);
    expect(daysBetween('2026-10-15', '2026-10-14')).toBe(-1);
  });

  it('counts whole days across the daylight-saving changes', () => {
    expect(daysBetween('2026-10-24', '2026-10-26')).toBe(2);
    expect(daysBetween('2026-03-28', '2026-03-30')).toBe(2);
  });

  it('adds and subtracts days as dates', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31');
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29');
  });
});

describe('nextPuzzleAt', () => {
  it('is the next Berlin midnight on an ordinary day', () => {
    expect(nextPuzzleAt(at('2026-10-15T10:00:00Z')).toISOString()).toBe(
      '2026-10-15T22:00:00.000Z',
    );
    expect(nextPuzzleAt(at('2026-12-15T10:00:00Z')).toISOString()).toBe(
      '2026-12-15T23:00:00.000Z',
    );
  });

  it('is exactly one full day away right at midnight', () => {
    const midnight = at('2026-10-14T22:00:00Z'); // 00:00 on 15 October
    expect(nextPuzzleAt(midnight).toISOString()).toBe(
      '2026-10-15T22:00:00.000Z',
    );
  });

  it('is still ahead one millisecond before midnight', () => {
    const almost = at('2026-10-15T21:59:59.999Z');
    expect(nextPuzzleAt(almost).toISOString()).toBe('2026-10-15T22:00:00.000Z');
  });

  it('copes with the 25-hour day when the clocks go back (25 Oct 2026)', () => {
    const start = at('2026-10-24T22:00:00Z'); // 00:00 CEST
    const next = nextPuzzleAt(start);
    expect(next.toISOString()).toBe('2026-10-25T23:00:00.000Z'); // 00:00 CET
    expect((next.getTime() - start.getTime()) / 3_600_000).toBe(25);
  });

  it('copes with the 23-hour day when the clocks go forward (29 Mar 2026)', () => {
    const start = at('2026-03-28T23:00:00Z'); // 00:00 CET
    const next = nextPuzzleAt(start);
    expect(next.toISOString()).toBe('2026-03-29T22:00:00.000Z'); // 00:00 CEST
    expect((next.getTime() - start.getTime()) / 3_600_000).toBe(23);
  });
});
