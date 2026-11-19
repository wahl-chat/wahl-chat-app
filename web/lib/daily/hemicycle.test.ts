import { describe, expect, it } from 'bun:test';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import {
  isUnaffiliated,
  layoutHemicycle,
  layoutShare,
  rowCount,
  seatsPerRow,
  voteBreakdown,
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

  it('gives each tile its logo, its own unless another is set', () => {
    const arcs = layoutHemicycle([
      { ...party('cdu', 2, 0), logo_id: 'cdu_csu' },
      party('spd', 1, 0),
    ]).arcs;
    expect(Object.fromEntries(arcs.map((a) => [a.partyId, a.logoId]))).toEqual({
      cdu: 'cdu_csu',
      spd: 'spd',
    });
  });

  it('skips parties without members and handles an empty vote', () => {
    expect(layoutHemicycle([party('spd', 0, 0)]).seats).toEqual([]);
    expect(
      layoutHemicycle([party('spd', 1, 0), party('x', 0, 0)]).arcs,
    ).toHaveLength(1);
  });
});

describe('isUnaffiliated', () => {
  it('marks members without a Fraktion', () => {
    expect(isUnaffiliated('fraktionslos')).toBe(true);
    expect(isUnaffiliated('spd')).toBe(false);
  });
});

describe('votesInOrder', () => {
  it('groups a party by how it voted', () => {
    expect(votesInOrder(party('fraktionslos', 1, 2, 1, 1))).toEqual([
      'yes',
      'abstain',
      'no',
      'no',
      'absent',
    ]);
  });
});

describe('rowCount', () => {
  it('uses ten rows for a Bundestag-sized chamber', () => {
    expect(rowCount(630)).toBe(10);
  });
});

describe('voteBreakdown', () => {
  it("counts one Fraktion's votes, members without a vote as Nicht beteiligt", () => {
    expect(voteBreakdown(party('spd', 110, 3, 1, 6))).toEqual([
      { vote: 'yes', count: 110 },
      { vote: 'no', count: 3 },
      { vote: 'abstain', count: 1 },
      { vote: 'absent', count: 6 },
    ]);
  });
});

describe('layoutShare', () => {
  const split = (accept: number, reject: number) => {
    const { seats } = layoutShare(accept, reject);
    const count = (vote: string) => seats.filter((s) => s.vote === vote).length;
    return {
      total: seats.length,
      yes: count('yes'),
      no: count('no'),
      absent: count('absent'),
    };
  };

  it('always draws a hundred seats', () => {
    expect(split(796, 488).total).toBe(100);
    expect(split(0, 0).total).toBe(100);
  });

  it('splits the seats by share', () => {
    expect(split(796, 488)).toEqual({ total: 100, yes: 62, no: 38, absent: 0 });
    expect(split(1, 0)).toEqual({ total: 100, yes: 100, no: 0, absent: 0 });
  });

  it('never rounds a side with votes away', () => {
    expect(split(1, 400).yes).toBe(1);
    expect(split(400, 1).no).toBe(1);
  });

  it('draws no votes as hollow seats', () => {
    expect(split(0, 0)).toEqual({ total: 100, yes: 0, no: 0, absent: 100 });
  });

  it('puts Annehmen on the left', () => {
    const { seats } = layoutShare(50, 50);
    const left = seats.filter((s) => s.x < -0.5);
    expect(left.every((s) => s.vote === 'yes')).toBe(true);
  });
});
