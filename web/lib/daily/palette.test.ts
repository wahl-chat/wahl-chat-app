import { describe, expect, it } from 'bun:test';
import { SEAT_FILLS, TOPIC_COLORS } from './palette';
import { DAILY_TOPIC_KEYS } from './topics';

describe('palette', () => {
  it('has a colour for every feed topic', () => {
    expect(Object.keys(TOPIC_COLORS).sort()).toEqual(
      [...DAILY_TOPIC_KEYS].sort(),
    );
  });

  it('keeps the seat colours apart', () => {
    const fills = Object.values(SEAT_FILLS);
    expect(new Set(fills).size).toBe(fills.length);
  });
});
