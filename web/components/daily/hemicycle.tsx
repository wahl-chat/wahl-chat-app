'use client';

import {
  type PartyArc,
  type SeatVote,
  VOTE_LABELS,
  isUnaffiliated,
  layoutHemicycle,
  voteBreakdown,
  voteTotals,
} from '@/lib/daily/hemicycle';
import { SEAT_FILLS } from '@/lib/daily/palette';
import type { DigestVoteParty } from '@/lib/firebase/firebase.types';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import { useMemo, useState } from 'react';

// Other Fraktionen fade back while one is selected.
const DIMMED_OPACITY = 0.18;

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

function FactionMarker({
  arc,
  dimmed,
  onSelect,
}: {
  arc: PartyArc;
  dimmed: boolean;
  onSelect?: () => void;
}) {
  const [missing, setMissing] = useState(false);
  const angle = (arc.startAngle + arc.endAngle) / 2;
  const x = MARKER_RADIUS * Math.cos(angle) - MARKER_W / 2;
  const y = -MARKER_RADIUS * Math.sin(angle) - MARKER_H / 2;
  return (
    // Pointer only: the Fraktion list under the chart is the keyboard path.
    // biome-ignore lint/a11y/useKeyWithClickEvents: see above
    // biome-ignore lint/nursery/noStaticElementInteractions: see above
    <g
      onClick={onSelect}
      opacity={dimmed ? DIMMED_OPACITY : 1}
      className={cn(onSelect && 'cursor-pointer')}
    >
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
          href={buildPartyImageUrl(arc.logoId)}
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
  /** The Fraktion whose block stays lit while the others fade. */
  selected?: string | null;
  /** Makes each Fraktion's block and marker clickable. */
  onSelect?: (partyId: string) => void;
};

/**
 * One dot per member, coloured by their vote. Per-member votes are not in the
 * data, so each faction's block is filled from its counts (Ja, Enthalten,
 * Nein, Nicht beteiligt, left to right): the split is exact, the seat is not.
 */
export function Hemicycle({ parties, className, selected, onSelect }: Props) {
  const layout = useMemo(() => layoutHemicycle(parties), [parties]);
  const totals = useMemo(() => voteTotals(parties), [parties]);
  const r = layout.seatRadius;

  const dimmed = (partyId: string) => Boolean(selected) && partyId !== selected;

  const label = `Abstimmungsergebnis: ${totals.yes} Ja, ${totals.no} Nein, ${totals.abstain} Enthaltungen, ${totals.absent} nicht beteiligt. ${layout.arcs
    .map((a) => `${a.name}: ${a.seats} Sitze`)
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
          // Pointer only: the Fraktion list under the chart is the keyboard path.
          // biome-ignore lint/a11y/useKeyWithClickEvents: see above
          // biome-ignore lint/nursery/noStaticElementInteractions: see above
          <circle
            // Seats have no identity beyond their position in the layout.
            // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
            key={i}
            onClick={onSelect && (() => onSelect(seat.partyId))}
            opacity={dimmed(seat.partyId) ? DIMMED_OPACITY : 1}
            className={cn(onSelect && 'cursor-pointer')}
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
          <FactionMarker
            key={arc.partyId}
            arc={arc}
            dimmed={dimmed(arc.partyId)}
            onSelect={onSelect && (() => onSelect(arc.partyId))}
          />
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
          Ja : Nein
        </text>
      </g>
    </svg>
  );
}

/** Counted key under the chart: "● 318 Ja  ● 284 Nein  ● 4 Enthalten  ○ 24 Nicht beteiligt". */
export function SeatLegend({
  parties,
  className,
}: {
  parties: DigestVoteParty[];
  className?: string;
}) {
  const totals = voteTotals(parties);
  return (
    <ul
      className={cn(
        'flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[15px] tabular-nums',
        className,
      )}
    >
      {(Object.keys(VOTE_LABELS) as SeatVote[]).map((vote) => (
        <li key={vote} className="flex items-center gap-1.5">
          <VoteSwatch vote={vote} />
          {totals[vote]} {VOTE_LABELS[vote]}
        </li>
      ))}
    </ul>
  );
}

function VoteSwatch({ vote }: { vote: SeatVote }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2.5 shrink-0 rounded-full"
      style={
        vote === 'absent'
          ? { boxShadow: `inset 0 0 0 1px ${ABSENT_RING}` }
          : { backgroundColor: SEAT_FILLS[vote] }
      }
    />
  );
}

/** How the members of one Fraktion voted: the four counts and a bar that
 * splits the Fraktion by them. */
export function PartyVoteBreakdown({
  party,
  id,
}: {
  party: DigestVoteParty;
  id?: string;
}) {
  const shares = voteBreakdown(party);
  const total = shares.reduce((sum, s) => sum + s.count, 0);
  return (
    <section
      id={id}
      aria-live="polite"
      className="flex flex-col gap-2 rounded-xl bg-[var(--daily-surface)] p-4"
    >
      <h4 className="text-[15px] font-semibold">
        So hat {party.name} gestimmt
        <span className="font-normal text-[var(--daily-muted)]">
          {' '}
          · {total} Abgeordnete
        </span>
      </h4>
      {total > 0 && (
        <div aria-hidden className="flex h-2 overflow-hidden rounded-full">
          {shares
            .filter((s) => s.count > 0)
            .map((s) => (
              <span
                key={s.vote}
                style={{
                  flexGrow: s.count,
                  backgroundColor:
                    s.vote === 'absent'
                      ? 'var(--daily-border)'
                      : SEAT_FILLS[s.vote],
                }}
              />
            ))}
        </div>
      )}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[15px] tabular-nums">
        {shares.map((s) => (
          <li key={s.vote} className="flex items-center gap-1.5">
            <VoteSwatch vote={s.vote} />
            {s.count} {s.label}
          </li>
        ))}
      </ul>
    </section>
  );
}
