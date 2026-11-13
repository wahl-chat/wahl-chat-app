import {
  type PartyState,
  type SeatLook,
  chamberLabel,
  partyState,
  seatLook,
} from '@/lib/stimmts/chamber-state';
import {
  BAND_INNER,
  BAND_OUTER,
  BAND_OUTER_ACTIVE,
  type PartyBand,
  TILE_HEIGHT,
  TILE_PADDING,
  TILE_WIDTH,
  chamberViewBox,
  layoutChamber,
  partyBands,
  ringSegment,
  tileOrigin,
} from '@/lib/stimmts/hemicycle';
import { partyLabel } from '@/lib/stimmts/labels';
import { partyFillClass, partyLogo } from '@/lib/stimmts/parties';
import type { PartyResult } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import { useMemo } from 'react';

/** How long one wedge takes to turn over, seat by seat from its left edge. */
const FLIP_SPREAD_MS = 650;

// A guess is a ring, the truth is a fill: the difference lets the player see
// their prediction against reality without reading.
const SEAT_CLASSES: Record<SeatLook, string> = {
  pending: 'fill-seat-pending stroke-transparent',
  active: 'fill-muted-foreground stroke-transparent',
  'guess-yes': 'fill-background stroke-seat-yes',
  'guess-no': 'fill-background stroke-seat-no',
  'guess-abstain': 'fill-background stroke-seat-abstain',
  yes: 'fill-seat-yes stroke-transparent',
  no: 'fill-seat-no stroke-transparent',
  abstain: 'fill-seat-abstain stroke-transparent',
  absent: 'fill-background stroke-seat-absent-ring',
  unaffiliated: 'fill-seat-unaffiliated stroke-transparent',
};

const fixed = (n: number) => n.toFixed(4);

type Props = {
  /** In seating order, left to right. */
  parties: readonly PartyResult[];
  /** Members without a Fraktion, drawn at the right end and never changed. */
  unaffiliated: number;
  /** By party; a party without an entry is pending. */
  states: Record<string, PartyState>;
  /** The hollow centre: a big line and a small one. */
  center: { big: string; small: string };
  /** Called for parties whose state is tappable (pointer only). */
  onPartyClick?: (partyId: string) => void;
};

/**
 * The Bundestag as one dot per member: the board of Stimmt's?. Each party has
 * a band in its colour along its wedge and its logo on a tile; seats show the
 * player's guess as rings and the real vote, once revealed, as a fill.
 */
function Hemicycle({
  parties,
  unaffiliated,
  states,
  center,
  onPartyClick,
}: Props) {
  const layout = useMemo(
    () => layoutChamber(parties, unaffiliated),
    [parties, unaffiliated],
  );
  const bands = useMemo(
    () => partyBands(layout, unaffiliated),
    [layout, unaffiliated],
  );
  const r = layout.seatRadius;

  return (
    <svg
      viewBox={chamberViewBox(bands)}
      role="img"
      aria-label={chamberLabel(parties, states, unaffiliated)}
      className="block w-full overflow-visible"
    >
      {layout.seats.map((seat) => {
        const state =
          seat.partyId === null ? undefined : partyState(states, seat.partyId);
        const look = state ? seatLook(seat, state) : 'unaffiliated';
        // The delay only matters when a seat changes, so a party revealed
        // before the page opened appears at once rather than as a wave.
        const delay =
          state?.mode === 'revealed'
            ? Math.round(seat.order * FLIP_SPREAD_MS)
            : 0;
        return (
          <circle
            key={`${fixed(seat.x)},${fixed(seat.y)}`}
            cx={fixed(seat.x)}
            cy={fixed(-seat.y)}
            r={fixed(
              look === 'unaffiliated'
                ? r * 0.85
                : look === 'absent'
                  ? r * 0.8
                  : r,
            )}
            strokeWidth={fixed(r * 0.45)}
            style={{ transitionDelay: `${delay}ms` }}
            className={cn(
              'transition-[fill,stroke] duration-300 ease-out motion-reduce:transition-none',
              SEAT_CLASSES[look],
            )}
          />
        );
      })}

      {bands.map((band) => (
        <PartyMarker
          key={band.partyId}
          band={band}
          state={partyState(states, band.partyId)}
          onClick={onPartyClick}
        />
      ))}

      <g textAnchor="middle" aria-hidden>
        <text
          y={-0.1}
          fontSize={0.13}
          className="fill-foreground font-display font-extrabold"
        >
          {center.big}
        </text>
        <text y={-0.01} fontSize={0.075} className="fill-muted-foreground">
          {center.small}
        </text>
      </g>
    </svg>
  );
}

type MarkerProps = {
  band: PartyBand;
  state: PartyState;
  onClick?: (partyId: string) => void;
};

/**
 * A party's band and logo tile, tappable when the party can be revealed.
 * Pointer only: to a screen reader the chamber is one image, and the list
 * under it ("Deine Tipps") offers the same action as real buttons.
 */
function PartyMarker({ band, state, onClick }: MarkerProps) {
  const { partyId } = band;
  const tappable =
    (state.mode === 'guessed' || state.mode === 'revealed') &&
    !!state.tappable &&
    !!onClick;
  const active = state.mode === 'active';
  const dim = state.mode === 'pending' && !!state.dim;
  const { x, y } = tileOrigin(band);

  const activate = () => {
    if (tappable) {
      onClick?.(partyId);
    }
  };

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: a pointer shortcut; the list under the chamber is the keyboard path.
    // biome-ignore lint/nursery/noStaticElementInteractions: as above.
    <g
      data-active={active}
      className={cn(
        'group transition-opacity duration-200 motion-reduce:transition-none',
        dim && 'opacity-40',
        tappable && 'cursor-pointer',
      )}
      onClick={tappable ? activate : undefined}
    >
      <title>{partyLabel(partyId)}</title>
      {/* A generous invisible area, so the whole wedge edge can be tapped. */}
      <path
        d={ringSegment(
          BAND_INNER - 0.05,
          band.tileRadius + 0.12,
          band.from,
          band.to,
        )}
        className="fill-transparent"
      />
      <path
        d={ringSegment(
          BAND_INNER,
          active ? BAND_OUTER_ACTIVE : BAND_OUTER,
          band.from,
          band.to,
        )}
        className={cn(
          partyFillClass(partyId),
          tappable && 'group-hover:opacity-85',
        )}
      />
      <rect
        x={fixed(x - 0.02)}
        y={fixed(y - 0.02)}
        width={fixed(TILE_WIDTH + 0.04)}
        height={fixed(TILE_HEIGHT + 0.04)}
        rx={0.05}
        strokeWidth={0.012}
        className="fill-none stroke-transparent group-data-[active=true]:stroke-foreground"
      />
      <rect
        x={fixed(x)}
        y={fixed(y)}
        width={TILE_WIDTH}
        height={TILE_HEIGHT}
        rx={0.035}
        className={cn(
          partyFillClass(partyId),
          tappable && 'group-hover:opacity-85',
        )}
      />
      <image
        href={partyLogo(partyId)}
        x={fixed(x + TILE_PADDING)}
        y={fixed(y + TILE_PADDING)}
        width={fixed(TILE_WIDTH - 2 * TILE_PADDING)}
        height={fixed(TILE_HEIGHT - 2 * TILE_PADDING)}
        preserveAspectRatio="xMidYMid meet"
      />
    </g>
  );
}

export default Hemicycle;
