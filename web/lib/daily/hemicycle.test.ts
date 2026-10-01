import { describe, expect, it } from 'bun:test';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import {
  isCloseVote,
  layoutArcLabels,
  layoutHemicycle,
  rowCount,
  seatsPerRow,
  splitUnaffiliated,
  voteTotals,
  votesInOrder,
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

describe('isCloseVote', () => {
  it('flags ties and narrow margins', () => {
    expect(isCloseVote([party('a', 50, 50)])).toBe(true);
    expect(isCloseVote([party('a', 51, 49)])).toBe(true);
  });

  it('ignores clear results and empty votes', () => {
    expect(isCloseVote([party('a', 318, 284)])).toBe(false);
    expect(isCloseVote([party('a', 400, 100)])).toBe(false);
    expect(isCloseVote([party('a', 0, 0, 3, 2)])).toBe(false);
  });

  it('only weighs Ja against Nein', () => {
    expect(isCloseVote([party('a', 51, 49, 300, 200)])).toBe(true);
  });
});

describe('layoutArcLabels', () => {
  const options = { radius: 1.15, fontSize: 0.07 };

  function labels(parties: DigestVoteParty[]) {
    return layoutArcLabels(layoutHemicycle(parties).arcs, options);
  }

  it('centres a label over its block when there is room', () => {
    const [label] = labels([party('spd', 100, 0)]);
    const mid = (label.startAngle + label.endAngle) / 2;
    expect(mid).toBeCloseTo(Math.PI / 2, 2);
  });

  it('never lets neighbouring labels overlap, even for tiny blocks', () => {
    const placed = labels(BUNDESTAG);
    // Left to right means descending angles.
    for (let i = 1; i < placed.length; i++) {
      expect(placed[i].startAngle).toBeLessThanOrEqual(placed[i - 1].endAngle);
    }
  });

  it('keeps labels close to the chamber ends', () => {
    for (const label of labels(BUNDESTAG)) {
      expect(label.startAngle).toBeLessThanOrEqual(Math.PI + 0.12 + 1e-9);
      expect(label.endAngle).toBeGreaterThanOrEqual(-0.12 - 1e-9);
    }
  });
});

describe('splitUnaffiliated', () => {
  it('takes fraktionslose members out of the chamber', () => {
    const { seated, unaffiliated } = splitUnaffiliated(BUNDESTAG);
    expect(unaffiliated.map((p) => p.party_id)).toEqual(['fraktionslos']);
    expect(seated.some((p) => p.party_id === 'fraktionslos')).toBe(false);
    expect(seated).toHaveLength(BUNDESTAG.length - 1);
  });

  it('lists their votes in the chamber order', () => {
    expect(votesInOrder(party('fraktionslos', 1, 2, 1, 1))).toEqual([
      'yes',
      'abstain',
      'no',
      'no',
      'absent',
    ]);
  });
});
