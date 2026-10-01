import {
  type SeatVote,
  layoutHemicycle,
  voteTotals,
} from '@/lib/daily/hemicycle';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useMemo } from 'react';

export const SEAT_COLORS: Record<SeatVote, string> = {
  yes: 'hsl(var(--chart-yes))',
  abstain: 'hsl(var(--seat-abstain))',
  no: 'hsl(var(--chart-no))',
  absent: 'hsl(var(--seat-absent))',
};

export const SEAT_LABELS: Record<SeatVote, string> = {
  yes: 'Ja',
  abstain: 'Enthalten',
  no: 'Nein',
  absent: 'Abwesend',
};

const ARC_RADIUS = 1.06;
const ARC_WIDTH = 0.045;
// Angular gap between neighbouring party arcs, so blocks read as separate.
const ARC_GAP = 0.012;

// Fixed precision so the server-rendered SVG and the hydrating client agree
// to the character; raw trig results can differ in their last digits.
function coord(value: number): string {
  return value.toFixed(4);
}

function arcPath(radius: number, from: number, to: number): string {
  const point = (angle: number) =>
    `${coord(radius * Math.cos(angle))} ${coord(-radius * Math.sin(angle))}`;
  // From the left end to the right end over the top is clockwise on screen.
  return `M ${point(from)} A ${radius} ${radius} 0 0 1 ${point(to)}`;
}

type Props = {
  parties: DigestVoteParty[];
  className?: string;
};

export function Hemicycle({ parties, className }: Props) {
  const layout = useMemo(() => layoutHemicycle(parties), [parties]);
  const totals = useMemo(() => voteTotals(parties), [parties]);
  const pad = layout.seatRadius / ARC_RADIUS;

  const label = `Abstimmungsergebnis: ${totals.yes} Ja, ${totals.no} Nein, ${totals.abstain} Enthaltungen, ${totals.absent} abwesend. ${layout.arcs
    .map((a) => `${a.name}: ${a.seats} Sitze`)
    .join(', ')}.`;

  return (
    <svg
      viewBox="-1.12 -1.12 2.24 1.16"
      className={cn('w-full', className)}
      role="img"
      aria-label={label}
    >
      {layout.arcs.map((arc) => {
        const from = arc.startAngle + pad - ARC_GAP;
        const to = arc.endAngle - pad + ARC_GAP;
        const d = arcPath(ARC_RADIUS, Math.max(from, to), Math.min(from, to));
        return (
          <g key={arc.partyId}>
            {/* Outline keeps white and near-black party colours visible in both themes. */}
            <path
              d={d}
              fill="none"
              stroke="hsl(var(--border))"
              strokeWidth={ARC_WIDTH + 0.014}
            />
            <path d={d} fill="none" stroke={arc.color} strokeWidth={ARC_WIDTH}>
              <title>{`${arc.name}: ${arc.seats}`}</title>
            </path>
          </g>
        );
      })}
      {layout.seats.map((seat, i) => (
        <circle
          // Seats have no identity beyond their position in the layout.
          // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
          key={i}
          cx={coord(seat.x)}
          cy={coord(-seat.y)}
          r={coord(layout.seatRadius)}
          fill={SEAT_COLORS[seat.vote]}
        />
      ))}
    </svg>
  );
}

export function SeatLegend({ className }: { className?: string }) {
  return (
    <ul
      className={cn(
        'flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground',
        className,
      )}
    >
      {(Object.keys(SEAT_COLORS) as SeatVote[]).map((vote) => (
        <li key={vote} className="flex items-center gap-1">
          <span
            className="inline-block size-2.5 rounded-full"
            style={{ backgroundColor: SEAT_COLORS[vote] }}
          />
          {SEAT_LABELS[vote]}
        </li>
      ))}
    </ul>
  );
}
