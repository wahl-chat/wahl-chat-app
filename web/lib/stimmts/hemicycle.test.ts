import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import {
  BAND_OUTER_ACTIVE,
  TILE_CLEARANCE,
  TILE_HEIGHT,
  TILE_WIDTH,
  chamberViewBox,
  layoutChamber,
  partyBands,
  rowCount,
  seatsPerRow,
  tileDistance,
  tileOrigin,
} from './hemicycle';

const puzzle = PUZZLES[0];
const layout = layoutChamber(puzzle.parties, puzzle.unaffiliated);
const bands = partyBands(layout, puzzle.unaffiliated);

describe('seatsPerRow', () => {
  it.each([1, 7, 97, 157, 630])('places exactly %i seats', (total) => {
    const counts = seatsPerRow(total, rowCount(total));
    expect(counts.reduce((a, b) => a + b, 0)).toBe(total);
    expect(counts.every((c) => c >= 1)).toBe(true);
  });
});

describe('layoutChamber', () => {
  it('draws all 630 seats, the members without a Fraktion included', () => {
    expect(layout.seats).toHaveLength(630);
    expect(layout.seats.filter((seat) => seat.partyId === null)).toHaveLength(
      3,
    );
  });

  it('seats the members without a Fraktion at the right end', () => {
    const rightmost = Math.min(...layout.seats.map((seat) => seat.angle));
    const unaffiliated = layout.seats.filter((seat) => seat.partyId === null);
    for (const seat of unaffiliated) {
      expect(seat.angle).toBeLessThan(layout.arcs[4].startAngle);
    }
    expect(unaffiliated.some((seat) => seat.angle === rightmost)).toBe(true);
  });

  it('keeps the parties in seating order, each in one wedge', () => {
    expect(layout.arcs.map((arc) => arc.partyId)).toEqual([
      'linke',
      'spd',
      'gruene',
      'cdu',
      'afd',
    ]);
    const order = layout.seats
      .map((seat) => seat.partyId)
      .filter((id) => id !== null);
    const runs = order.filter((id, i) => i === 0 || order[i - 1] !== id);
    expect(runs).toHaveLength(5);
  });

  it('groups each wedge by vote and runs the wave from left to right', () => {
    const spd = layout.seats.filter((seat) => seat.partyId === 'spd');
    expect(spd.filter((seat) => seat.vote === 'yes')).toHaveLength(116);
    expect(spd.at(-1)?.vote).toBe('absent');
    expect(spd[0].order).toBe(0);
    expect(spd.at(-1)?.order).toBe(1);
  });
});

describe('partyBands', () => {
  it('gives every party a band, left to right, without overlaps', () => {
    expect(bands.map((band) => band.partyId)).toEqual(
      layout.arcs.map((arc) => arc.partyId),
    );
    for (let i = 1; i < bands.length; i++) {
      expect(bands[i].from).toBeLessThan(bands[i - 1].to);
    }
  });

  it('keeps every logo tile the same small gap from the band', () => {
    const clear = BAND_OUTER_ACTIVE + TILE_CLEARANCE;
    for (const band of bands) {
      const gap = tileDistance(band.tileRadius, band.middle);
      expect(gap).toBeGreaterThanOrEqual(clear);
      expect(gap).toBeLessThan(clear + 0.006);
    }
  });

  it('sets a top tile closer in than a side tile', () => {
    const top = bands.find((band) => band.partyId === 'gruene');
    const side = bands.find((band) => band.partyId === 'linke');
    expect(top?.tileRadius).toBeLessThan(side?.tileRadius ?? 0);
  });
});

describe('chamberViewBox', () => {
  it('fits every tile', () => {
    const [minX, minY, width, height] = chamberViewBox(bands)
      .split(' ')
      .map(Number);
    for (const band of bands) {
      const { x, y } = tileOrigin(band);
      expect(x).toBeGreaterThanOrEqual(minX);
      expect(y).toBeGreaterThanOrEqual(minY);
      expect(x + TILE_WIDTH).toBeLessThanOrEqual(minX + width);
      expect(y + TILE_HEIGHT).toBeLessThanOrEqual(minY + height);
    }
  });
});
