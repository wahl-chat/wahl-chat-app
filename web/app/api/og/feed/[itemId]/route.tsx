import {
  ABSENT_RING,
  type SeatVote,
  layoutHemicycle,
  seatShape,
  voteTotals,
} from '@/lib/daily/hemicycle';
import { getLinkedItem } from '@/lib/daily/linked-item';
import { SEAT_FILLS } from '@/lib/daily/palette';
import { OG_IMAGE_SIZE } from '@/lib/daily/share-metadata';
import { resolveLocale } from '@/lib/seo';
import { getTranslations } from 'next-intl/server';
import { ImageResponse } from 'next/og';

// The seats span x ∈ [-1, 1] and y ∈ [-1, 0] plus a seat radius; no room is
// kept for the Fraktion logos, which are WebP and cannot be drawn here.
const VIEW_BOX = { x: -1.05, y: -1.05, width: 2.1, height: 1.08 };
const CHART_WIDTH = 1000;
const UNIT = CHART_WIDTH / VIEW_BOX.width;
const CHART_HEIGHT = Math.round(VIEW_BOX.height * UNIT);

const INK = '#18181B';
const MUTED = '#52525B';

const LEGEND: SeatVote[] = ['yes', 'no', 'abstain', 'absent'];

function LegendSwatch({ vote }: { vote: SeatVote }) {
  return (
    <div
      style={{
        width: 26,
        height: 26,
        borderRadius: 13,
        ...(vote === 'absent'
          ? { backgroundColor: '#FFFFFF', border: `5px solid ${ABSENT_RING}` }
          : { backgroundColor: SEAT_FILLS[vote] }),
      }}
    />
  );
}

/** A shared vote's link preview: the chamber with every seat coloured by how
 * its member voted, as the detail view draws it. */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ itemId: string }> },
) {
  const { itemId } = await params;
  const locale = resolveLocale(
    new URL(request.url).searchParams.get('locale') ?? undefined,
  );
  const t = await getTranslations({ locale, namespace: 'feed' });
  const item = await getLinkedItem(itemId, locale);
  if (item?.kind !== 'vote') {
    return new Response('Not found', { status: 404 });
  }

  const { parties } = item.vote;
  const layout = layoutHemicycle(parties);
  const totals = voteTotals(parties);

  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 24,
        backgroundColor: '#FFFFFF',
        color: INK,
      }}
    >
      <div
        style={{
          position: 'relative',
          display: 'flex',
          width: CHART_WIDTH,
          height: CHART_HEIGHT,
        }}
      >
        <svg
          width={CHART_WIDTH}
          height={CHART_HEIGHT}
          viewBox={`${VIEW_BOX.x} ${VIEW_BOX.y} ${VIEW_BOX.width} ${VIEW_BOX.height}`}
        >
          {layout.seats.map((seat, i) => (
            // Seats have no identity beyond their position in the layout.
            // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
            <circle key={i} {...seatShape(seat, layout.seatRadius)} />
          ))}
        </svg>
        {/* In the hollow centre, as in the detail view. Text inside the SVG
            would not be drawn. */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0.08 * UNIT,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: 0.14 * UNIT, fontWeight: 700 }}>
            {`${totals.yes} : ${totals.no}`}
          </div>
          <div style={{ fontSize: 0.075 * UNIT, color: MUTED }}>
            {t('yesNo')}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 40, fontSize: 30, color: MUTED }}>
        {LEGEND.map((vote) => (
          <div
            key={vote}
            style={{ display: 'flex', alignItems: 'center', gap: 12 }}
          >
            <LegendSwatch vote={vote} />
            {`${t(`seat.${vote}`)} ${totals[vote]}`}
          </div>
        ))}
      </div>
    </div>,
    {
      ...OG_IMAGE_SIZE,
      // A day, not the default year: a corrected count must reach previews.
      headers: { 'Cache-Control': 'public, max-age=86400' },
    },
  );
}
