import { describe, expect, it } from 'bun:test';
import { flipTransform } from './flip';

describe('flipTransform', () => {
  it('moves the card centre onto the icon centre at the icon width', () => {
    const card = { x: 16, y: 120, width: 343, height: 100 };
    const icon = { x: 250, y: 10, width: 44, height: 44 };
    const { x, y, scale } = flipTransform(card, icon);
    expect(scale).toBeCloseTo(44 / 343, 10);
    // Card centre (187.5, 170) onto icon centre (272, 32).
    expect(x).toBeCloseTo(84.5, 10);
    expect(y).toBeCloseTo(-138, 10);
  });

  it('is the identity between equal rects', () => {
    const rect = { x: 5, y: 6, width: 7, height: 8 };
    expect(flipTransform(rect, rect)).toEqual({ x: 0, y: 0, scale: 1 });
  });

  it('does not divide by a zero width', () => {
    const empty = { x: 0, y: 0, width: 0, height: 0 };
    const icon = { x: 1, y: 1, width: 2, height: 2 };
    expect(flipTransform(empty, icon).scale).toBe(1);
  });
});
