import { describe, expect, it } from 'bun:test';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import {
  layoutHemicycle,
  rowCount,
  seatsPerRow,
  voteTotals,
} from './hemicycle';

function party(
  party_id: string,
  yes: number,
  no: number,
  abstain = 0,
  no_show = 0,
): DigestVoteParty {
  return {
    party_id,
    name: party_id.toUpperCase(),
    color: '#000000',
    yes,
    no,
    abstain,
    no_show,
  };
}

const BUNDESTAG = [
  party('afd', 0, 140, 0, 12),
  party('cdu', 200, 0, 0, 8),
  party('spd', 110, 3, 1, 6),
  party('gruene', 0, 60, 20, 5),
  party('linke', 0, 60, 0, 4),
  party('fraktionslos', 0, 1, 0, 1),
];

describe('seatsPerRow', () => {
  it.each([1, 7, 97, 157, 630])('places exactly %i seats', (total) => {
    const counts = seatsPerRow(total, rowCount(total));
    expect(counts.reduce((a, b) => a + b, 0)).toBe(total);
    expect(counts.every((c) => c >= 1)).toBe(true);
  });

  it('gives outer rows at least as many seats as inner ones', () => {
    const counts = seatsPerRow(630, rowCount(630));
    for (let i = 1; i < counts.length; i++) {
      expect(counts[i]).toBeGreaterThanOrEqual(counts[i - 1]);
    }
  });
});

describe('layoutHemicycle', () => {
  const layout = layoutHemicycle(BUNDESTAG);

  it('draws one seat per member', () => {
    expect(layout.seats).toHaveLength(voteTotals(BUNDESTAG).total);
  });

  it('orders party wedges left to right, unaffiliated members last', () => {
    expect(layout.arcs.map((a) => a.partyId)).toEqual([
      'linke',
      'spd',
      'gruene',
      'cdu',
      'afd',
      'fraktionslos',
    ]);
  });

  it('keeps each party in one contiguous wedge', () => {
    const order = layout.seats.map((s) => s.partyId);
    const runs = order.filter((p, i) => i === 0 || order[i - 1] !== p);
    expect(new Set(runs).size).toBe(runs.length);
  });

  it('groups each party by vote: yes, abstain, no, absent', () => {
    const spd = layout.seats
      .filter((s) => s.partyId === 'spd')
      .map((s) => s.vote);
    const runs = spd.filter((v, i) => i === 0 || spd[i - 1] !== v);
    expect(runs).toEqual(['yes', 'abstain', 'no', 'absent']);
    expect(spd.filter((v) => v === 'yes')).toHaveLength(110);
  });

  it('keeps seats inside the unit half disc', () => {
    for (const seat of layout.seats) {
      expect(Math.hypot(seat.x, seat.y)).toBeLessThanOrEqual(1);
      expect(seat.y).toBeGreaterThanOrEqual(-1e-9);
    }
  });

  it('skips parties without members and handles an empty vote', () => {
    expect(layoutHemicycle([party('spd', 0, 0)]).seats).toEqual([]);
    expect(
      layoutHemicycle([party('spd', 1, 0), party('x', 0, 0)]).arcs,
    ).toHaveLength(1);
  });
});
