import { describe, expect, it } from 'bun:test';
import { SEAT_FILLS, TOPIC_SWATCHES } from './palette';
import { DAILY_TOPIC_KEYS } from './topics';

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('palette', () => {
  it('has a swatch for every feed topic', () => {
    expect(Object.keys(TOPIC_SWATCHES).sort()).toEqual(
      [...DAILY_TOPIC_KEYS].sort(),
    );
  });

  it.each(Object.entries(TOPIC_SWATCHES))(
    '%s tag text meets WCAG AA on its fill',
    (_topic, { fill, fg }) => {
      expect(contrast(fill, fg)).toBeGreaterThanOrEqual(4.5);
    },
  );

  it('keeps the seat colours apart', () => {
    const fills = Object.values(SEAT_FILLS);
    expect(new Set(fills).size).toBe(fills.length);
  });
});
