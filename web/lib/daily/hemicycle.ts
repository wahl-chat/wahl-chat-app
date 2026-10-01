import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import { sortBySeating } from './seating-order';

export type SeatVote = 'yes' | 'abstain' | 'no' | 'absent';

export type Seat = {
  x: number;
  y: number;
  /** Polar angle of the seat (π = far left, 0 = far right). */
  angle: number;
  partyId: string;
  vote: SeatVote;
};

export type PartyArc = {
  partyId: string;
  name: string;
  color: string;
  startAngle: number;
  endAngle: number;
  seats: number;
};

export type HemicycleLayout = {
  seats: Seat[];
  arcs: PartyArc[];
  seatRadius: number;
};

/** Inner radius of the half ring, as a fraction of the outer radius. Wide
 * enough that the seat legend fits in the hollow centre. */
export const INNER_RADIUS = 0.5;

/** Order of the vote blocks inside each party wedge, left to right. */
const VOTE_ORDER: SeatVote[] = ['yes', 'abstain', 'no', 'absent'];

export function seatCount(party: DigestVoteParty): number {
  return party.yes + party.no + party.abstain + party.no_show;
}

/**
 * Number of rows that keeps seats roughly as far apart along each arc as the
 * rows are from each other. With rows of width d between INNER_RADIUS and 1
 * and seats spaced ~d along each arc, the ring holds about
 * π·rows²·(1+r₀) / (2·(1−r₀)) seats; solving for rows gives this.
 */
export function rowCount(totalSeats: number): number {
  if (totalSeats <= 0) {
    return 0;
  }
  const rows = Math.sqrt(
    (2 * totalSeats * (1 - INNER_RADIUS)) / (Math.PI * (1 + INNER_RADIUS)),
  );
  return Math.max(1, Math.min(totalSeats, Math.round(rows)));
}

/** Seats per row, proportional to each row's radius, summing exactly. */
export function seatsPerRow(totalSeats: number, rows: number): number[] {
  if (rows === 0) {
    return [];
  }
  const radii = rowRadii(rows);
  const radiusSum = radii.reduce((a, b) => a + b, 0);
  const counts = radii.map((r) =>
    Math.max(1, Math.floor((totalSeats * r) / radiusSum)),
  );
  // Hand the rounding remainder to the outer rows, which have the most room.
  let remainder = totalSeats - counts.reduce((a, b) => a + b, 0);
  for (let i = rows - 1; remainder > 0; i = (i - 1 + rows) % rows) {
    counts[i] += 1;
    remainder -= 1;
  }
  for (let i = 0; remainder < 0; i = (i + 1) % rows) {
    if (counts[i] > 1) {
      counts[i] -= 1;
      remainder += 1;
    }
  }
  return counts;
}

function rowRadii(rows: number): number[] {
  const width = (1 - INNER_RADIUS) / rows;
  return Array.from(
    { length: rows },
    (_, i) => INNER_RADIUS + width * (i + 0.5),
  );
}

type Position = { x: number; y: number; angle: number; radius: number };

function seatPositions(totalSeats: number): {
  positions: Position[];
  rowWidth: number;
} {
  const rows = rowCount(totalSeats);
  const radii = rowRadii(rows);
  const counts = seatsPerRow(totalSeats, rows);
  const positions: Position[] = [];
  counts.forEach((count, row) => {
    const radius = radii[row];
    for (let j = 0; j < count; j++) {
      const angle = count === 1 ? Math.PI / 2 : Math.PI * (1 - j / (count - 1));
      positions.push({
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
        angle,
        radius,
      });
    }
  });
  // Sweeping by angle (left first) turns consecutive seats into wedges, so a
  // party's block spans every row like in a real plenary hall.
  positions.sort((a, b) => b.angle - a.angle || a.radius - b.radius);
  return { positions, rowWidth: rows ? (1 - INNER_RADIUS) / rows : 0 };
}

export function votesInOrder(party: DigestVoteParty): SeatVote[] {
  const counts: Record<SeatVote, number> = {
    yes: party.yes,
    abstain: party.abstain,
    no: party.no,
    absent: party.no_show,
  };
  return VOTE_ORDER.flatMap((vote) =>
    Array.from({ length: counts[vote] }, () => vote),
  );
}

/**
 * Lay out one seat per member: party wedges in seating order, and inside each
 * wedge the members grouped by how they voted. Coordinates are in a unit half
 * disc (x ∈ [-1, 1], y ∈ [0, 1], y pointing up).
 */
export function layoutHemicycle(
  parties: readonly DigestVoteParty[],
): HemicycleLayout {
  const ordered = sortBySeating(parties).filter((p) => seatCount(p) > 0);
  const total = ordered.reduce((sum, p) => sum + seatCount(p), 0);
  const { positions, rowWidth } = seatPositions(total);

  const seats: Seat[] = [];
  const arcs: PartyArc[] = [];
  let cursor = 0;
  for (const party of ordered) {
    const votes = votesInOrder(party);
    const block = positions.slice(cursor, cursor + votes.length);
    block.forEach((position, i) => {
      seats.push({
        x: position.x,
        y: position.y,
        angle: position.angle,
        partyId: party.party_id,
        vote: votes[i],
      });
    });
    arcs.push({
      partyId: party.party_id,
      name: party.name,
      color: party.color,
      startAngle: block[0].angle,
      endAngle: block[block.length - 1].angle,
      seats: votes.length,
    });
    cursor += votes.length;
  }
  return { seats, arcs, seatRadius: rowWidth * 0.4 };
}

export type VoteTotals = Record<SeatVote, number> & { total: number };

export function voteTotals(parties: readonly DigestVoteParty[]): VoteTotals {
  const totals = { yes: 0, abstain: 0, no: 0, absent: 0, total: 0 };
  for (const p of parties) {
    totals.yes += p.yes;
    totals.abstain += p.abstain;
    totals.no += p.no;
    totals.absent += p.no_show;
  }
  totals.total = totals.yes + totals.abstain + totals.no + totals.absent;
  return totals;
}

/** Margin under which a vote counts as close: Ja and Nein within 5% of the
 * votes cast for either (at 10%, ordinary coalition majorities qualified).
 * Abstentions and absences are ignored. */
const CLOSE_VOTE_MARGIN = 0.05;

export function isCloseVote(parties: readonly DigestVoteParty[]): boolean {
  const { yes, no } = voteTotals(parties);
  const decided = yes + no;
  return decided > 0 && Math.abs(yes - no) / decided < CLOSE_VOTE_MARGIN;
}

export type ArcLabel = {
  partyId: string;
  name: string;
  /** Angular extent of the label text (startAngle > endAngle, like arcs). */
  startAngle: number;
  endAngle: number;
};

type LabelOptions = {
  radius: number;
  fontSize: number;
  /** Average glyph advance as a fraction of the font size. */
  charWidth?: number;
  /** Minimum angular gap between neighbouring labels. */
  gap?: number;
  /** How far past the chamber's ends (in radians) a label may run. */
  overhang?: number;
};

/**
 * Place each party's name along the outside of the chamber, centred over its
 * block where there is room. Small blocks (a handful of fraktionslose seats)
 * get labels wider than themselves, so neighbours are pushed apart along the
 * arc: one sweep left to right resolves overlaps, a second right to left pulls
 * labels back inside the chamber's end.
 */
export function layoutArcLabels(
  arcs: readonly PartyArc[],
  {
    radius,
    fontSize,
    charWidth = 0.56,
    gap = 0.03,
    overhang = 0.12,
  }: LabelOptions,
): ArcLabel[] {
  // Work in "distance from the left end" (0 … π), which grows left to right.
  const items = arcs.map((arc) => {
    const width = (arc.name.length * fontSize * charWidth) / radius;
    const centre = Math.PI - (arc.startAngle + arc.endAngle) / 2;
    return { arc, width, left: centre - width / 2 };
  });
  items.sort((a, b) => a.left + a.width / 2 - (b.left + b.width / 2));

  const minLeft = -overhang;
  const maxRight = Math.PI + overhang;
  let previousRight = Number.NEGATIVE_INFINITY;
  for (const item of items) {
    item.left = Math.max(item.left, previousRight + gap, minLeft);
    previousRight = item.left + item.width;
  }
  let nextLeft = Number.POSITIVE_INFINITY;
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    const right = Math.min(item.left + item.width, nextLeft - gap, maxRight);
    item.left = right - item.width;
    nextLeft = item.left;
  }

  return items.map(({ arc, width, left }) => ({
    partyId: arc.partyId,
    name: arc.name,
    startAngle: Math.PI - left,
    endAngle: Math.PI - (left + width),
  }));
}

/** Members without a Fraktion. They have no block in the chamber, so they are
 * drawn as a separate row instead of a wedge. */
const UNAFFILIATED = new Set(['fraktionslos', 'fraktionslose']);

export function splitUnaffiliated(parties: readonly DigestVoteParty[]): {
  seated: DigestVoteParty[];
  unaffiliated: DigestVoteParty[];
} {
  const seated: DigestVoteParty[] = [];
  const unaffiliated: DigestVoteParty[] = [];
  for (const party of parties) {
    (UNAFFILIATED.has(party.party_id) ? unaffiliated : seated).push(party);
  }
  return { seated, unaffiliated };
}
