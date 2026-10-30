import { type DayRecord, PERIOD_LENGTH } from './period';

// The Stimmt's? mark is a minimal chamber of 30 seats in three rows, the
// length of a Wahlperiode: the player's own period is drawn in the same
// shape and fills it day by day.
const MARK_ROWS = [
  { radius: 0.55, seats: 7 },
  { radius: 0.775, seats: 10 },
  { radius: 1, seats: 13 },
];

/** Radius of one seat of the mark, in the unit half disc. */
export const MARK_SEAT_RADIUS = 0.085;

/** The SVG viewBox of the mark and of a Wahlperiode. */
export const MARK_VIEWBOX = '-1.1 -1.1 2.2 1.2';

/** The logo's vote colour for a seat: Nein left, Enthaltung on top, Ja right. */
export type MarkTone = 'no' | 'abstain' | 'yes';

type MarkSeat = {
  /** SVG coordinates (y down). */
  x: number;
  y: number;
  tone: MarkTone;
};

function toneAt(t: number): MarkTone {
  return t < 0.42 ? 'no' : t < 0.55 ? 'abstain' : 'yes';
}

/**
 * The 30 seats in day order: day 1 on the far left, day 30 on the far right,
 * sweeping across the three rows like a party's wedge in the big chamber.
 */
export const MARK_SEATS: MarkSeat[] = MARK_ROWS.flatMap((row) =>
  Array.from({ length: row.seats }, (_, j) => {
    const t = j / (row.seats - 1);
    const angle = Math.PI * (1 - t);
    return {
      angle,
      radius: row.radius,
      seat: {
        x: row.radius * Math.cos(angle),
        y: -row.radius * Math.sin(angle),
        tone: toneAt(t),
      },
    };
  }),
)
  .sort((a, b) => b.angle - a.angle || a.radius - b.radius)
  .map(({ seat }) => seat);

/** A day's seat, darker the better the score (never a vote colour). */
export type ScoreTier = 'low' | 'mid' | 'top';

export function scoreTier(score: number): ScoreTier {
  return score >= 5 ? 'top' : score >= 3 ? 'mid' : 'low';
}

export type PeriodSeat = MarkSeat &
  (
    | { kind: 'played'; day: DayRecord & { kind: 'played' }; tier: ScoreTier }
    | { kind: 'missed'; day: DayRecord & { kind: 'missed' } }
    /** Today's card is still in hand. */
    | { kind: 'today' }
    | { kind: 'future' }
  );

/**
 * Every seat of a Wahlperiode, from the period's days so far (see
 * currentWahlperiode). With all 30 days played, the seats take the logo's
 * colours (`complete`); otherwise played seats carry their score tier.
 */
export function periodSeats(
  days: DayRecord[],
  todayInHand: boolean,
): PeriodSeat[] {
  return MARK_SEATS.slice(0, PERIOD_LENGTH).map((seat, index) => {
    const day = days[index];
    if (day?.kind === 'played') {
      return { ...seat, kind: 'played', day, tier: scoreTier(day.score) };
    }
    if (day?.kind === 'missed') {
      return { ...seat, kind: 'missed', day };
    }
    if (index === days.length && todayInHand) {
      return { ...seat, kind: 'today' };
    }
    return { ...seat, kind: 'future' };
  });
}
