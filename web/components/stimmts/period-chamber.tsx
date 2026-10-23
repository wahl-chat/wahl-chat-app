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
  /** Index of the seat whose card is shown. */
  selected?: number | null;
  /** Index of the seat that just filled, which pops in. */
  fresh?: number | null;
  /** Makes played seats buttons that show that day's card. */
  onSelect?: (index: number) => void;
  className?: string;
};

/** The player's Wahlperiode, drawn in the shape of the Stimmt's? logo. */
function PeriodChamber({
  seats,
  complete = false,
  selected = null,
  fresh = null,
  onSelect,
  className,
}: Props) {
  return (
    <svg
      viewBox={MARK_VIEWBOX}
      aria-hidden={!onSelect}
      className={cn('block w-full overflow-visible', className)}
    >
      {seats.map((seat, index) => {
        const common = {
          cx: fixed(seat.x),
          cy: fixed(seat.y),
          r: MARK_SEAT_RADIUS,
        };
        const key = `${fixed(seat.x)},${fixed(seat.y)}`;
        if (seat.kind === 'played') {
          const isSelected = selected === index;
          const label = `Nr. ${seat.day.number}, ${seat.day.score} von 5 richtig`;
          const select = () => onSelect?.(index);
          const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              select();
            }
          };
          return (
            <circle
              key={key}
              {...common}
              strokeWidth={0.03}
              className={cn(
                'transition-[fill,stroke] duration-300 motion-reduce:transition-none',
                complete ? LOGO_CLASSES[seat.tone] : TIER_CLASSES[seat.tier],
                isSelected ? 'stroke-brand-red' : 'stroke-transparent',
                onSelect &&
                  'cursor-pointer outline-none focus-visible:stroke-ring',
                fresh === index &&
                  'origin-center animate-stimmts-seat-pop [transform-box:fill-box] motion-reduce:animate-none',
              )}
              {...(onSelect
                ? {
                    role: 'button',
                    tabIndex: 0,
                    'aria-label': label,
                    'aria-pressed': isSelected,
                    onClick: select,
                    onKeyDown,
                  }
                : {})}
            >
              <title>{label}</title>
            </circle>
          );
        }
        if (seat.kind === 'missed') {
          return (
            <circle
              key={key}
              {...common}
              strokeWidth={0.02}
              className="fill-transparent stroke-seat-absent-ring [stroke-dasharray:0.03_0.025]"
            >
              <title>Nr. {seat.day.number}: verpasst</title>
            </circle>
          );
        }
        if (seat.kind === 'today') {
          return (
            <circle
              key={key}
              {...common}
              strokeWidth={0.022}
              className="animate-stimmts-breathe fill-transparent stroke-foreground [stroke-dasharray:0.04_0.028] motion-reduce:animate-none"
            />
          );
        }
        return (
          <circle
            key={key}
            {...common}
            strokeWidth={0.018}
            className="fill-transparent stroke-seat-pending"
          />
        );
      })}
    </svg>
  );
}

export default PeriodChamber;
