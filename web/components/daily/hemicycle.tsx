import {
  type SeatVote,
  layoutArcLabels,
  layoutHemicycle,
  splitUnaffiliated,
  voteTotals,
  votesInOrder,
} from '@/lib/daily/hemicycle';
import { SEAT_FILLS, partyColor } from '@/lib/daily/palette';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useId, useMemo } from 'react';

export const SEAT_LABELS: Record<SeatVote, string> = {
  yes: 'Ja',
  abstain: 'Enthalten',
  no: 'Nein',
  absent: 'Abwesend',
};

const INK = 'var(--daily-ink)';

const ARC_RADIUS = 1.075;
const ARC_WIDTH = 0.07;
const ARC_OUTLINE = 0.022;
// Angular gap between neighbouring party bands, so blocks read as separate.
const ARC_GAP = 0.02;

// Seats are drawn as ticks: narrow along the row, long along the radius, so
// each row fans outward like a printed diagram rather than a dot grid. Sized
// against the layout's seat radius, which leaves deliberate air between them.
const TICK_WIDTH = 1.4;
const TICK_LENGTH = 1.85;

// Party names run along the outside of the bands.
const LABEL_RADIUS = 1.15;
const LABEL_FONT = 0.068;
const LABEL_OVERHANG = 0.06;

const BODY_FONT = { fontFamily: 'var(--font-daily-body)' };

// Fraktionslose members sit in a row below the chamber's right end (under the
// rightmost block), right-aligned with the outer band.
const ROW_RIGHT = 1.12;
const ROW_TOP = 0.13;
const ROW_MAX_WIDTH = 1.0;
const ROW_GAP_FACTOR = 0.55;
const ROW_LINE_GAP = 0.03;

// The chamber itself ends just below its baseline.
const VIEWBOX_TOP = -1.23;
const CHAMBER_BOTTOM = 0.08;

// The seat legend sits in the hollow centre, one entry per row, shortest on
// top where the hollow is narrowest.
const LEGEND_ORDER: SeatVote[] = ['yes', 'no', 'abstain', 'absent'];
const LEGEND_FONT = 0.068;
const LEGEND_LEFT = -0.21;
const LEGEND_TOP_BASELINE = -0.3;
const LEGEND_LINE = 0.085;

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

/** Screen rotation that points a vertical tick along the seat's radius. */
function tickRotation(angle: number): string {
  return coord(90 - (angle * 180) / Math.PI);
}

type Props = {
  parties: DigestVoteParty[];
  className?: string;
};

export function Hemicycle({ parties, className }: Props) {
  const { seated, unaffiliated } = useMemo(
    () => splitUnaffiliated(parties),
    [parties],
  );
  const layout = useMemo(() => layoutHemicycle(seated), [seated]);
  const totals = useMemo(() => voteTotals(parties), [parties]);
  const pad = layout.seatRadius / ARC_RADIUS;
  const tickW = layout.seatRadius * TICK_WIDTH;
  const tickL = layout.seatRadius * TICK_LENGTH;
  const labels = useMemo(
    () =>
      layoutArcLabels(layout.arcs, {
        radius: LABEL_RADIUS,
        fontSize: LABEL_FONT,
        overhang: LABEL_OVERHANG,
      }),
    [layout.arcs],
  );
  // useId output may contain characters that are awkward inside url(#…).
  const pathPrefix = `hc${useId().replace(/[^a-zA-Z0-9]/g, '')}`;

  const rows = useMemo(
    () => layoutUnaffiliatedRows(unaffiliated, tickW, tickL),
    [unaffiliated, tickW, tickL],
  );
  const bottom = rows.length
    ? Math.max(...rows.map((r) => r.y + tickL)) + 0.05
    : CHAMBER_BOTTOM;

  const label = `Abstimmungsergebnis: ${totals.yes} Ja, ${totals.no} Nein, ${totals.abstain} Enthaltungen, ${totals.absent} abwesend. ${[
    ...layout.arcs.map((a) => `${a.name}: ${a.seats} Sitze`),
    ...unaffiliated.map((p) => `${p.name}: ${votesInOrder(p).length}`),
  ].join(', ')}.`;

  return (
    <svg
      viewBox={`-1.23 ${VIEWBOX_TOP} 2.46 ${coord(bottom - VIEWBOX_TOP)}`}
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
            <path
              d={d}
              fill="none"
              style={{ stroke: INK }}
              strokeWidth={ARC_WIDTH + ARC_OUTLINE}
            />
            <path
              d={d}
              fill="none"
              style={{ stroke: partyColor(arc.partyId, arc.color) }}
              strokeWidth={ARC_WIDTH}
            >
              <title>{`${arc.name}: ${arc.seats}`}</title>
            </path>
          </g>
        );
      })}

      <defs>
        {labels.map((l) => (
          <path
            key={l.partyId}
            id={`${pathPrefix}-${l.partyId}`}
            d={arcPath(LABEL_RADIUS, l.startAngle, l.endAngle)}
          />
        ))}
      </defs>
      <g
        style={{ ...BODY_FONT, fill: INK }}
        fontSize={LABEL_FONT}
        fontWeight="700"
      >
        {labels.map((l) => (
          <text key={l.partyId} textAnchor="middle">
            <textPath href={`#${pathPrefix}-${l.partyId}`} startOffset="50%">
              {l.name}
            </textPath>
          </text>
        ))}
      </g>

      {layout.seats.map((seat, i) => {
        const cx = seat.x;
        const cy = -seat.y;
        const absent = seat.vote === 'absent';
        return (
          <rect
            // Seats have no identity beyond their position in the layout.
            // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
            key={i}
            x={coord(cx - tickW / 2)}
            y={coord(cy - tickL / 2)}
            width={coord(tickW)}
            height={coord(tickL)}
            rx={coord(tickW * 0.3)}
            transform={`rotate(${tickRotation(seat.angle)} ${coord(cx)} ${coord(cy)})`}
            fill={
              absent ? 'none' : SEAT_FILLS[seat.vote as keyof typeof SEAT_FILLS]
            }
            style={absent ? { stroke: INK, strokeOpacity: 0.45 } : undefined}
            strokeWidth={absent ? coord(tickW * 0.22) : undefined}
          />
        );
      })}

      {rows.map((row) => (
        <g key={`${row.partyId}-${row.y}`}>
          {row.label && (
            <text
              x={coord(row.x - 0.04)}
              y={coord(row.y + tickL * 0.78)}
              textAnchor="end"
              fontSize={LABEL_FONT}
              fontWeight="700"
              style={{ ...BODY_FONT, fill: INK }}
            >
              {row.label}:
            </text>
          )}
          {row.votes.map((vote, i) => {
            const absent = vote === 'absent';
            return (
              <rect
                // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
                key={i}
                x={coord(row.x + i * row.pitch)}
                y={coord(row.y)}
                width={coord(tickW)}
                height={coord(tickL)}
                rx={coord(tickW * 0.3)}
                fill={
                  absent ? 'none' : SEAT_FILLS[vote as keyof typeof SEAT_FILLS]
                }
                style={
                  absent ? { stroke: INK, strokeOpacity: 0.45 } : undefined
                }
                strokeWidth={absent ? coord(tickW * 0.22) : undefined}
              />
            );
          })}
        </g>
      ))}

      <SeatLegendInset />
    </svg>
  );
}

type UnaffiliatedRow = {
  partyId: string;
  /** Only the first row of a group carries the name. */
  label: string | null;
  votes: ReturnType<typeof votesInOrder>;
  x: number;
  y: number;
  pitch: number;
};

/** Rows of upright seat ticks, right-aligned, wrapping when a group is long. */
function layoutUnaffiliatedRows(
  parties: readonly DigestVoteParty[],
  tickW: number,
  tickL: number,
): UnaffiliatedRow[] {
  const pitch = tickW * (1 + ROW_GAP_FACTOR);
  const perRow = Math.max(1, Math.floor(ROW_MAX_WIDTH / pitch));
  const rows: UnaffiliatedRow[] = [];
  let y = ROW_TOP;
  for (const party of parties) {
    const votes = votesInOrder(party);
    for (let start = 0; start < votes.length; start += perRow) {
      const chunk = votes.slice(start, start + perRow);
      const width = Math.min(votes.length, perRow) * pitch - (pitch - tickW);
      rows.push({
        partyId: party.party_id,
        label: start === 0 ? party.name : null,
        votes: chunk,
        x: ROW_RIGHT - width,
        y,
        pitch,
      });
      y += tickL + ROW_LINE_GAP;
    }
  }
  return rows;
}

/** Ja/Nein/Enthalten/Abwesend key, drawn inside the hollow of the chamber. */
function SeatLegendInset() {
  const swatchW = LEGEND_FONT * 0.6;
  const swatchH = LEGEND_FONT * 0.95;
  return (
    <g
      style={{ ...BODY_FONT, fill: INK }}
      fontSize={LEGEND_FONT}
      fontWeight="600"
    >
      {LEGEND_ORDER.map((vote, i) => {
        const baseline = LEGEND_TOP_BASELINE + i * LEGEND_LINE;
        const absent = vote === 'absent';
        return (
          <g key={vote}>
            <rect
              x={coord(LEGEND_LEFT)}
              y={coord(baseline - swatchH * 0.85)}
              width={coord(swatchW)}
              height={coord(swatchH)}
              rx={coord(swatchW * 0.3)}
              fill={
                absent ? 'none' : SEAT_FILLS[vote as keyof typeof SEAT_FILLS]
              }
              style={absent ? { stroke: INK, strokeOpacity: 0.45 } : undefined}
              strokeWidth={absent ? coord(swatchW * 0.22) : undefined}
            />
            <text x={coord(LEGEND_LEFT + swatchW * 2)} y={coord(baseline)}>
              {SEAT_LABELS[vote]}
            </text>
          </g>
        );
      })}
    </g>
  );
}

/** The headline result under the chart, numbers and words at one size. */
export function VoteTally({ parties }: { parties: DigestVoteParty[] }) {
  const totals = voteTotals(parties);
  return (
    <p className="flex flex-wrap items-baseline justify-center gap-x-3 font-display text-3xl font-black tabular-nums leading-none">
      <span>{totals.yes} Ja</span>
      <span aria-hidden>:</span>
      <span>{totals.no} Nein</span>
    </p>
  );
}

export function SeatLegend({ className }: { className?: string }) {
  return (
    <ul
      className={cn(
        'flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-medium text-[var(--daily-muted)]',
        className,
      )}
    >
      {(Object.keys(SEAT_LABELS) as SeatVote[]).map((vote) => (
        <li key={vote} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn(
              'inline-block h-3 w-2 rounded-[2px]',
              vote === 'absent' &&
                'border-[1.5px] border-[color-mix(in_srgb,var(--daily-ink)_45%,transparent)]',
            )}
            style={
              vote === 'absent'
                ? undefined
                : { backgroundColor: SEAT_FILLS[vote] }
            }
          />
          {SEAT_LABELS[vote]}
        </li>
      ))}
    </ul>
  );
}
