import { PERIOD_LENGTH } from '@/lib/stimmts/period';
import { cn } from '@/lib/utils';
import type { Ref } from 'react';

const CARD_WIDTH = 40;
const CARD_HEIGHT = 24;

/** Columns on the urn's floor, filled from the middle outwards. */
const COLUMNS = [2, 3, 1, 4, 0, 5];

/**
 * Where the n-th card lies on the urn's floor: six to a layer, from the
 * middle out, each layer a little higher, each card nudged and turned its own
 * way so the pile looks thrown in rather than stacked. Fixed per index (a
 * small hash, not chance), so the pile looks the same on every visit.
 */
function cardSpot(index: number) {
  const layer = Math.floor(index / COLUMNS.length);
  const column = COLUMNS[index % COLUMNS.length];
  const hash = (index * 2_654_435_761) % 1000;
  return {
    x: 68 + column * 20 + (layer % 2) * 6 + ((hash % 9) - 4),
    y: 188 - layer * 11 + (hash % 6),
    angle: (hash % 56) - 28,
  };
}

type Props = {
  /** Stimmkarten cast in this Wahlperiode so far. */
  cards: number;
  /** The last card was just cast: it drops onto the pile. */
  freshCard?: boolean;
  /** The slot in the lid, which the cast card flies into. */
  slotRef?: Ref<SVGPolygonElement>;
};

/**
 * A glass ballot box, drawn in outline, with the player's Stimmkarten of the
 * current Wahlperiode lying inside. The cards are drawn in the Stimmkarte's
 * own ink, so they read as the cards the player cast.
 */
function Urn({ cards, freshCard = false, slotRef }: Props) {
  const shown = Math.min(cards, PERIOD_LENGTH);
  return (
    <svg
      viewBox="0 36 240 182"
      aria-hidden
      className="mx-auto block w-56 overflow-visible text-foreground"
    >
      {/* The glass, and its hidden back edges. */}
      <path d="M40 70 H200 V210 H40 Z" className="fill-foreground/[0.04]" />
      <path
        d="M70 40 V180 L40 210 M70 180 H230"
        fill="none"
        strokeWidth={1.5}
        strokeDasharray="4 5"
        className="stroke-muted-foreground/50"
      />
      {Array.from({ length: shown }, (_, index) => {
        const { x, y, angle } = cardSpot(index);
        const dropping = freshCard && index === shown - 1;
        return (
          <g
            // biome-ignore lint/suspicious/noArrayIndexKey: a card's place is its index.
            key={index}
            transform={`translate(${x} ${y})`}
          >
            <g
              className={cn(
                dropping &&
                  'animate-stimmts-card-drop motion-reduce:animate-none',
              )}
            >
              <rect
                x={-CARD_WIDTH / 2}
                y={-CARD_HEIGHT / 2}
                width={CARD_WIDTH}
                height={CARD_HEIGHT}
                rx={3}
                transform={`rotate(${angle})`}
                strokeWidth={1.5}
                className="fill-foreground stroke-background"
              />
            </g>
          </g>
        );
      })}
      {/* The front edges, drawn over the cards. */}
      <path
        d="M40 70 H200 V210 H40 Z M40 70 L70 40 H230 L200 70 M200 210 L230 180 V40"
        fill="none"
        strokeWidth={3}
        strokeLinejoin="round"
        strokeLinecap="round"
        className="stroke-foreground"
      />
      <polygon
        ref={slotRef}
        points="70,57.5 74,53.5 170,53.5 166,57.5"
        className="fill-foreground"
      />
    </svg>
  );
}

export default Urn;
