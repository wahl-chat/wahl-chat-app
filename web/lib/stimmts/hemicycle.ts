// The chamber's geometry: rows, seats per row, party wedges, and the bands
// and logo tiles around them.

import type { PartyResult } from './types';

export type SeatVote = 'yes' | 'abstain' | 'no' | 'absent';

export type Seat = {
  x: number;
  y: number;
  /** Polar angle of the seat (π = far left, 0 = far right). */
  angle: number;
  /** Null for a member without a Fraktion. */
  partyId: string | null;
  vote: SeatVote | null;
  /** 0 at the party's left edge to 1 at its right, for the reveal wave. */
  order: number;
};

export type PartyArc = {
  partyId: string;
  startAngle: number;
  endAngle: number;
  seats: number;
};

export type ChamberLayout = {
  seats: Seat[];
  arcs: PartyArc[];
  seatRadius: number;
};

/** Inner radius of the half ring, as a fraction of the outer radius. */
const INNER_RADIUS = 0.5;

/** Large chambers (the Bundestag) get a fixed row count, which keeps the dots
 * large enough to read at phone width. */
const LARGE_CHAMBER = 300;
const LARGE_CHAMBER_ROWS = 10;

/** Order of the vote blocks inside each party wedge, left to right. */
const VOTE_ORDER: SeatVote[] = ['yes', 'abstain', 'no', 'absent'];

export function seatCount(party: PartyResult): number {
  return party.yes + party.no + party.abstain + party.noShow;
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
  if (totalSeats >= LARGE_CHAMBER) {
    return LARGE_CHAMBER_ROWS;
  }
  const rows = Math.sqrt(
    (2 * totalSeats * (1 - INNER_RADIUS)) / (Math.PI * (1 + INNER_RADIUS)),
  );
  return Math.max(1, Math.min(totalSeats, Math.round(rows)));
}

function rowRadii(rows: number): number[] {
  const width = (1 - INNER_RADIUS) / rows;
  return Array.from(
    { length: rows },
    (_, i) => INNER_RADIUS + width * (i + 0.5),
  );
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

function votesInOrder(party: PartyResult): SeatVote[] {
  const counts: Record<SeatVote, number> = {
    yes: party.yes,
    abstain: party.abstain,
    no: party.no,
    absent: party.noShow,
  };
  return VOTE_ORDER.flatMap((vote) =>
    Array.from({ length: counts[vote] }, () => vote),
  );
}

/**
 * One seat per member: party wedges in the puzzle's (seating) order, members
 * grouped by vote inside each wedge, and the members without a Fraktion at
 * the right end. Coordinates are in a
 * unit half disc (x ∈ [-1, 1], y ∈ [0, 1], y pointing up).
 */
export function layoutChamber(
  parties: readonly PartyResult[],
  unaffiliated: number,
): ChamberLayout {
  const seated = parties.filter((party) => seatCount(party) > 0);
  const total =
    seated.reduce((sum, party) => sum + seatCount(party), 0) + unaffiliated;
  const { positions, rowWidth } = seatPositions(total);

  const seats: Seat[] = [];
  const arcs: PartyArc[] = [];
  let cursor = 0;
  for (const party of seated) {
    const votes = votesInOrder(party);
    const block = positions.slice(cursor, cursor + votes.length);
    block.forEach((position, i) => {
      seats.push({
        x: position.x,
        y: position.y,
        angle: position.angle,
        partyId: party.partyId,
        vote: votes[i],
        order: i / Math.max(1, votes.length - 1),
      });
    });
    arcs.push({
      partyId: party.partyId,
      startAngle: block[0].angle,
      endAngle: block[block.length - 1].angle,
      seats: votes.length,
    });
    cursor += votes.length;
  }
  for (const position of positions.slice(cursor)) {
    seats.push({
      x: position.x,
      y: position.y,
      angle: position.angle,
      partyId: null,
      vote: null,
      order: 0,
    });
  }
  return { seats, arcs, seatRadius: rowWidth * 0.4 };
}

// Each party wears a band in its colour along the outer row, and its logo
// on a tile centred on the wedge.
export const BAND_INNER = 1.03;
export const BAND_OUTER = 1.08;
/** The party being asked gets a thicker band. */
export const BAND_OUTER_ACTIVE = 1.11;
const BAND_GAP = 0.012;
export const TILE_WIDTH = 0.42;
export const TILE_HEIGHT = 0.27;
export const TILE_PADDING = 0.025;
/** The gap every tile keeps to the band, whatever its angle. */
export const TILE_CLEARANCE = 0.03;

export type PartyBand = {
  partyId: string;
  /** Angles of the band's ends (from > to: the band runs left to right). */
  from: number;
  to: number;
  /** Where the logo tile sits: centred on the band, this far out. */
  middle: number;
  tileRadius: number;
};

/** Distance from the chamber's centre to the nearest point of a tile. */
export function tileDistance(radius: number, angle: number): number {
  const cx = Math.abs(radius * Math.cos(angle));
  const cy = Math.abs(radius * Math.sin(angle));
  const dx = Math.max(cx - TILE_WIDTH / 2, 0);
  const dy = Math.max(cy - TILE_HEIGHT / 2, 0);
  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * How far out a tile at this angle sits: the smallest radius at which its
 * nearest edge clears the band (even the thicker band of the party being
 * asked) by TILE_CLEARANCE. Each tile gets its own. One shared radius would
 * be set by the side tiles (a wide tile beside the chamber reaches furthest
 * towards it) and leave the top ones floating far above their bands.
 */
export function tileRadius(angle: number): number {
  const clear = BAND_OUTER_ACTIVE + TILE_CLEARANCE;
  let radius = clear;
  while (tileDistance(radius, angle) < clear) {
    radius += 0.005;
  }
  return radius;
}

/**
 * The bands along the wedges. Wedges are not radial (each row splits at its
 * own angle), so a band ends halfway between one party's last seat and the
 * next one's first, with a small gap between neighbours.
 */
export function partyBands(
  layout: ChamberLayout,
  unaffiliated: number,
): PartyBand[] {
  const { arcs } = layout;
  if (arcs.length === 0) {
    return [];
  }
  const bounds = [Math.PI];
  for (let i = 1; i < arcs.length; i++) {
    bounds.push((arcs[i - 1].endAngle + arcs[i].startAngle) / 2);
  }
  const lastEnd = arcs[arcs.length - 1].endAngle;
  bounds.push(unaffiliated > 0 ? lastEnd - 0.012 : 0);

  return arcs.map((arc, i) => {
    const middle = (bounds[i] + bounds[i + 1]) / 2;
    const hasRightNeighbour = i < arcs.length - 1 || unaffiliated > 0;
    return {
      partyId: arc.partyId,
      from: bounds[i] - (i > 0 ? BAND_GAP / 2 : 0),
      to: bounds[i + 1] + (hasRightNeighbour ? BAND_GAP / 2 : 0),
      middle,
      tileRadius: tileRadius(middle),
    };
  });
}

/** Top-left corner of a band's logo tile, in SVG coordinates (y down). */
export function tileOrigin(band: PartyBand): { x: number; y: number } {
  return {
    x: band.tileRadius * Math.cos(band.middle) - TILE_WIDTH / 2,
    y: -band.tileRadius * Math.sin(band.middle) - TILE_HEIGHT / 2,
  };
}

const fixed = (n: number) => n.toFixed(4);

/** SVG path of a ring segment between two radii and two angles. */
export function ringSegment(
  inner: number,
  outer: number,
  from: number,
  to: number,
): string {
  const point = (r: number, a: number) =>
    `${fixed(r * Math.cos(a))} ${fixed(-r * Math.sin(a))}`;
  return [
    `M ${point(outer, from)}`,
    `A ${outer} ${outer} 0 0 1 ${point(outer, to)}`,
    `L ${point(inner, to)}`,
    `A ${inner} ${inner} 0 0 0 ${point(inner, from)}`,
    'Z',
  ].join(' ');
}

/** The SVG viewBox that fits the chamber, its bands and every logo tile. */
export function chamberViewBox(bands: PartyBand[]): string {
  const extent = { minX: -1.12, maxX: 1.12, minY: -1.12, maxY: 0.04 };
  for (const band of bands) {
    const { x, y } = tileOrigin(band);
    extent.minX = Math.min(extent.minX, x);
    extent.maxX = Math.max(extent.maxX, x + TILE_WIDTH);
    extent.minY = Math.min(extent.minY, y);
    extent.maxY = Math.max(extent.maxY, y + TILE_HEIGHT);
  }
  const margin = 0.04;
  return [
    extent.minX - margin,
    extent.minY - margin,
    extent.maxX - extent.minX + 2 * margin,
    extent.maxY - extent.minY + 2 * margin,
  ]
    .map(fixed)
    .join(' ');
}
