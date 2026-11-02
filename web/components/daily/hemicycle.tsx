'use client';

import {
  type PartyArc,
  type SeatVote,
  isUnaffiliated,
  layoutHemicycle,
  voteTotals,
} from '@/lib/daily/hemicycle';
import { SEAT_FILLS } from '@/lib/daily/palette';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';

const SEAT_ORDER: SeatVote[] = ['yes', 'no', 'abstain', 'absent'];

const ABSENT_RING = '#A1A1AA';

// Faction markers sit just outside the outer row, at the middle of the
// faction's block, like the seat labels in a printed Sitzverteilung.
// The tile is the party's own logo background (from the party seeds), which
// is what the site's logo files are drawn for.
const MARKER_RADIUS = 1.24;
const MARKER_W = 0.27;
const MARKER_H = 0.19;
const MARKER_PAD = 0.015;

// The score sits in the hollow centre, small enough to clear the inner row.
const SCORE_FONT = 0.13;
const SCORE_SUB_FONT = 0.075;

// Fixed precision so the server-rendered SVG and the hydrating client agree
// to the character; raw trig results can differ in their last digits.
function coord(value: number): string {
  return value.toFixed(4);
}

function FactionMarker({ arc }: { arc: PartyArc }) {
  const [missing, setMissing] = useState(false);
  const angle = (arc.startAngle + arc.endAngle) / 2;
  const x = MARKER_RADIUS * Math.cos(angle) - MARKER_W / 2;
  const y = -MARKER_RADIUS * Math.sin(angle) - MARKER_H / 2;
  return (
    <g>
      <rect
        x={coord(x)}
        y={coord(y)}
        width={MARKER_W}
        height={MARKER_H}
        rx={0.03}
        fill={arc.color}
      />
      {missing ? (
        <text
          x={coord(x + MARKER_W / 2)}
          y={coord(y + MARKER_H * 0.68)}
          textAnchor="middle"
          fontSize={0.065}
          fontWeight={800}
          fill="#FFFFFF"
        >
          {arc.name.slice(0, 5)}
        </text>
      ) : (
        <image
          href={buildPartyImageUrl(arc.partyId)}
          x={coord(x + MARKER_PAD)}
          y={coord(y + MARKER_PAD)}
          width={MARKER_W - 2 * MARKER_PAD}
          height={MARKER_H - 2 * MARKER_PAD}
          preserveAspectRatio="xMidYMid meet"
          onError={() => setMissing(true)}
        />
      )}
      <title>{arc.name}</title>
    </g>
  );
}

type Props = {
  parties: DigestVoteParty[];
  className?: string;
};

/**
 * One dot per member, coloured by their vote. Per-member votes are not in the
 * data, so each faction's block is filled from its counts (Ja, Enthalten,
 * Nein, Abwesend, left to right): the split is exact, the seat is not.
 */
export function Hemicycle({ parties, className }: Props) {
  const t = useTranslations('feed');
  const layout = useMemo(() => layoutHemicycle(parties), [parties]);
  const totals = useMemo(() => voteTotals(parties), [parties]);
  const r = layout.seatRadius;

  const label = `${t('voteResult', totals)} ${layout.arcs
    .map((a) => t('seats', { name: a.name, seats: a.seats }))
    .join(', ')}.`;

  return (
    <svg
      viewBox="-1.39 -1.37 2.78 1.42"
      className={cn('w-full', className)}
      role="img"
      aria-label={label}
    >
      {layout.seats.map((seat, i) => {
        const absent = seat.vote === 'absent';
        return (
          <circle
            // Seats have no identity beyond their position in the layout.
            // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
            key={i}
            cx={coord(seat.x)}
            cy={coord(-seat.y)}
            r={coord(absent ? r * 0.8 : r)}
            fill={
              absent
                ? '#FFFFFF'
                : SEAT_FILLS[seat.vote as keyof typeof SEAT_FILLS]
            }
            stroke={absent ? ABSENT_RING : undefined}
            strokeWidth={absent ? coord(r * 0.4) : undefined}
          />
        );
      })}

      {layout.arcs
        .filter((arc) => !isUnaffiliated(arc.partyId))
        .map((arc) => (
          <FactionMarker key={arc.partyId} arc={arc} />
        ))}

      <g aria-hidden textAnchor="middle" style={{ fill: 'var(--daily-ink)' }}>
        <text y={-0.1} fontSize={SCORE_FONT} fontWeight={700}>
          {totals.yes} : {totals.no}
        </text>
        <text
          y={-0.01}
          fontSize={SCORE_SUB_FONT}
          style={{ fill: 'var(--daily-muted)' }}
        >
          {t('yesNo')}
        </text>
      </g>
    </svg>
  );
}

/** Counted key under the chart: "● 318 Ja  ● 284 Nein  ● 4 Enthalten  ○ 24 Abwesend". */
export function SeatLegend({
  parties,
  className,
}: {
  parties: DigestVoteParty[];
  className?: string;
}) {
  const t = useTranslations('feed');
  const totals = voteTotals(parties);
  return (
    <ul
      className={cn(
        'flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[15px] tabular-nums',
        className,
      )}
    >
      {SEAT_ORDER.map((vote) => (
        <li key={vote} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block size-2.5 rounded-full"
            style={
              vote === 'absent'
                ? { boxShadow: `inset 0 0 0 1px ${ABSENT_RING}` }
                : { backgroundColor: SEAT_FILLS[vote] }
            }
          />
          {totals[vote]} {t(`seat.${vote}`)}
        </li>
      ))}
    </ul>
  );
}

// The gauge is a thick half ring; a hairline gap marks where Ja ends.
const GAUGE_RADIUS = 40;
const GAUGE_STROKE = 14;
const GAUGE_GAP = 0.03;

function gaugeArc(from: number, to: number): string {
  const point = (angle: number) =>
    `${coord(GAUGE_RADIUS * Math.cos(angle))} ${coord(-GAUGE_RADIUS * Math.sin(angle))}`;
  return `M ${point(from)} A ${GAUGE_RADIUS} ${GAUGE_RADIUS} 0 0 1 ${point(to)}`;
}

/**
 * The compact result: Ja against Nein as one half ring, Ja from the left like
 * the seat chart, with each count under its end of the ring. Abstentions and absences are
 * left out, since the outcome is decided between the two.
 */
export function VoteGauge({ parties }: { parties: DigestVoteParty[] }) {
  const t = useTranslations('feed');
  const { yes, no } = voteTotals(parties);
  const decided = yes + no;
  const split = decided > 0 ? Math.PI * (1 - yes / decided) : Math.PI / 2;
  const gap = yes > 0 && no > 0 ? GAUGE_GAP : 0;
  const extent = GAUGE_RADIUS + GAUGE_STROKE / 2;
  return (
    <figure className="flex w-32 flex-col items-center gap-1">
      <svg
        viewBox={`${-extent} ${-extent} ${2 * extent} ${extent}`}
        className="w-full"
        role="img"
        aria-label={`${yes} ${t('seat.yes')}, ${no} ${t('seat.no')}`}
      >
        {yes > 0 && (
          <path
            d={gaugeArc(Math.PI, split + gap)}
            fill="none"
            stroke={SEAT_FILLS.yes}
            strokeWidth={GAUGE_STROKE}
          />
        )}
        {no > 0 && (
          <path
            d={gaugeArc(split - gap, 0)}
            fill="none"
            stroke={SEAT_FILLS.no}
            strokeWidth={GAUGE_STROKE}
          />
        )}
      </svg>
      <figcaption
        aria-hidden
        className="flex w-full justify-between whitespace-nowrap text-[13px] font-semibold tabular-nums"
      >
        <span className="text-[var(--daily-yes)]">
          {yes} {t('seat.yes')}
        </span>
        <span className="text-[var(--daily-no)]">
          {no} {t('seat.no')}
        </span>
      </figcaption>
    </figure>
  );
}
