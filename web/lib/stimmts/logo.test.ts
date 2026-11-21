import { describe, expect, it } from 'bun:test';
import { MARK_SEATS, periodSeats, scoreTier } from './logo';
import type { DayRecord } from './period';

const played = (number: number, score: number): DayRecord => ({
  kind: 'played',
  number,
  playDate: '2026-11-01',
  topic: 'Energie',
  score,
});

describe('MARK_SEATS', () => {
  it('has the 30 seats of a Wahlperiode, from far left to far right', () => {
    expect(MARK_SEATS).toHaveLength(30);
    // Both ends sit on the floor line of the half disc.
    expect(MARK_SEATS[0].y).toBeCloseTo(0);
    expect(MARK_SEATS[0].x).toBeLessThan(0);
    expect(MARK_SEATS[29].y).toBeCloseTo(0);
    expect(MARK_SEATS[29].x).toBeGreaterThan(0);
  });

  it('keeps the logo order: Nein left, Enthaltung on top, Ja right', () => {
    expect(MARK_SEATS[0].tone).toBe('no');
    expect(MARK_SEATS[29].tone).toBe('yes');
    const top = MARK_SEATS.reduce((a, b) => (a.y < b.y ? a : b));
    expect(top.tone).toBe('abstain');
  });
});

describe('scoreTier', () => {
  it('darkens with the score', () => {
    expect([0, 2, 3, 4, 5].map(scoreTier)).toEqual([
      'low',
      'low',
      'mid',
      'mid',
      'top',
    ]);
  });
});

describe('periodSeats', () => {
  it('fills played and missed days, then today, then the future', () => {
    const days: DayRecord[] = [
      played(1, 5),
      { kind: 'missed', number: 2, playDate: '2026-11-02' },
    ];
    const seats = periodSeats(days, true);
    expect(seats.slice(0, 4).map((seat) => seat.kind)).toEqual([
      'played',
      'missed',
      'today',
      'future',
    ]);
    expect(seats[0]).toMatchObject({ kind: 'played', tier: 'top' });
  });

  it('has no dashed seat once today is cast', () => {
    const seats = periodSeats([played(1, 3)], false);
    expect(seats.some((seat) => seat.kind === 'today')).toBe(false);
  });
});
