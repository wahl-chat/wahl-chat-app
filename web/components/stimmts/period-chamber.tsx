import {
  MARK_SEAT_RADIUS,
  MARK_VIEWBOX,
  type MarkTone,
  type PeriodSeat,
  type ScoreTier,
} from '@/lib/stimmts/logo';
import { cn } from '@/lib/utils';
import type { KeyboardEvent } from 'react';

// A day's seat says how the player did, never how anyone voted, so it uses
// its own neutral tones; only a complete period takes the logo's colours.
const TIER_CLASSES: Record<ScoreTier, string> = {
  low: 'fill-tally-low',
  mid: 'fill-tally-mid',
  top: 'fill-tally-top',
};

const LOGO_CLASSES: Record<MarkTone, string> = {
  no: 'fill-seat-no',
  abstain: 'fill-seat-abstain',
  yes: 'fill-seat-yes',
};

const fixed = (n: number) => n.toFixed(4);

type Props = {
  seats: PeriodSeat[];
  /** All 30 days played. */
  complete?: boolean;
  /** Today's puzzle number, whose seat is ringed. */
  today: number;
  /** Opens a past day; played and missed seats before today are buttons. */
  onOpen?: (number: number) => void;
  /** Whether that day's puzzle can be shown (it may not be released). */
  canOpen?: (number: number) => boolean;
  className?: string;
};

function seatLabel(seat: PeriodSeat): string {
  if (seat.kind === 'played') {
    return `Nr. ${seat.day.number}, ${seat.day.score} von 5 richtig`;
  }
  if (seat.kind === 'missed') {
    return `Nr. ${seat.day.number}, verpasst`;
  }
  return 'Noch nicht gespielt';
}

/**
 * The player's Wahlperiode, drawn in the shape of the Stimmt's? logo: one
 * seat per day, darker the better the score, a dashed ring for a missed day.
 * It is the calendar of the period: a past day's seat opens that puzzle.
 */
function PeriodChamber({
  seats,
  complete = false,
  today,
  onOpen,
  canOpen = () => true,
  className,
}: Props) {
  return (
    <svg
      viewBox={MARK_VIEWBOX}
      aria-hidden={!onOpen}
      className={cn('block w-full overflow-visible', className)}
    >
      {seats.map((seat) => {
        const key = `${fixed(seat.x)},${fixed(seat.y)}`;
        const at = {
          cx: fixed(seat.x),
          cy: fixed(seat.y),
          r: MARK_SEAT_RADIUS,
        };
        const day = 'day' in seat ? seat.day : null;
        const isToday = day?.number === today;
        const openable =
          !!onOpen && !!day && day.number < today && canOpen(day.number);
        const open = () => day && onOpen?.(day.number);
        const onKeyDown = (event: KeyboardEvent) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            open();
          }
        };
        const label = seatLabel(seat);

        return (
          <circle
            key={key}
            {...at}
            strokeWidth={seat.kind === 'played' ? 0.03 : 0.02}
            className={cn(
              'outline-none',
              seat.kind === 'played' &&
                (complete ? LOGO_CLASSES[seat.tone] : TIER_CLASSES[seat.tier]),
              seat.kind === 'missed' &&
                'fill-transparent stroke-seat-absent-ring [stroke-dasharray:0.03_0.025]',
              (seat.kind === 'today' || seat.kind === 'future') &&
                'fill-transparent stroke-seat-pending',
              seat.kind === 'played' &&
                (isToday ? 'stroke-brand-red' : 'stroke-transparent'),
              openable &&
                'cursor-pointer hover:opacity-80 focus-visible:stroke-ring',
            )}
            {...(openable
              ? {
                  role: 'button',
                  tabIndex: 0,
                  'aria-label': `${label}. Rätsel ansehen`,
                  onClick: open,
                  onKeyDown,
                }
              : {})}
          >
            <title>{label}</title>
          </circle>
        );
      })}
    </svg>
  );
}

export default PeriodChamber;
