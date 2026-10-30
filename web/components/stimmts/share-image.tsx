// Rendered to PNG by next/og, not in the browser: only flexbox, absolute
// positioning, inline SVG and fixed colours work there, and every element
// with more than one child needs `display: flex`.

import {
  CHECK_RED,
  WORDMARK_PATHS,
  WORDMARK_VIEWBOX,
} from '@/components/chat/logo';
import { shortDay } from '@/lib/stimmts/labels';
import {
  MARK_SEATS,
  MARK_SEAT_RADIUS,
  MARK_VIEWBOX,
  type MarkTone,
  type ScoreTier,
  periodSeats,
} from '@/lib/stimmts/logo';
import { type DayRecord, PERIOD_LENGTH } from '@/lib/stimmts/period';
import {
  SHARE_COLORS as C,
  MAX_SCORE,
  type ShareImageData,
} from '@/lib/stimmts/share-image';

/** The font families the route registers. */
export const SHARE_FONTS = { display: 'Bricolage', sans: 'Arimo' } as const;

const QUESTION = 'Wie haben die Parteien im Bundestag abgestimmt?';

const MARK_FILLS: Record<MarkTone, string> = {
  no: C.seatNo,
  abstain: C.seatAbstain,
  yes: C.seatYes,
};

const TIER_FILLS: Record<ScoreTier, string> = {
  low: C.faint,
  mid: C.muted,
  top: C.ink,
};

// The mark's viewBox is 2.2 wide and 1.2 high.
const markHeight = (width: number) => Math.round((width * 1.2) / 2.2);

/** Every character the image can show, to cut the fonts down to. */
export function shareImageText(data: ShareImageData): string {
  return [
    "Stimmt's?’ STIMMKARTE Nr. von richtig getippt Abgestimmt Tag",
    'Schaffst du mehr? Jeden Tag ein neues Rätsel. wahl.chat/stimmts',
    QUESTION,
    data.result ? shortDay(data.result.playDate) : '',
    '0123456789',
  ].join(' ');
}

type Sizes = {
  padding: string;
  mark: number;
  word: number;
  cardPadding: string;
  cardGap: number;
  wordmark: number;
  score: number;
  right: number;
  square: number;
  squareGap: number;
  number: number;
  stamp: number;
  cta: number;
  url: number;
};

const SIZES: Record<ShareImageData['format'], Sizes> = {
  square: {
    padding: '72px 80px',
    mark: 140,
    word: 72,
    cardPadding: '44px 52px',
    cardGap: 24,
    wordmark: 200,
    score: 150,
    right: 34,
    square: 52,
    squareGap: 24,
    number: 120,
    stamp: 44,
    cta: 52,
    url: 32,
  },
  story: {
    padding: '140px 88px',
    mark: 380,
    word: 132,
    cardPadding: '44px 52px',
    cardGap: 24,
    wordmark: 220,
    score: 170,
    right: 34,
    square: 52,
    squareGap: 24,
    number: 120,
    stamp: 44,
    cta: 68,
    url: 32,
  },
  link: {
    padding: '52px 64px',
    mark: 110,
    word: 56,
    cardPadding: '30px 44px',
    cardGap: 14,
    wordmark: 150,
    score: 104,
    right: 28,
    square: 44,
    squareGap: 14,
    number: 92,
    stamp: 36,
    cta: 40,
    url: 28,
  },
};

function Mark({ width }: { width: number }) {
  return (
    <svg width={width} height={markHeight(width)} viewBox={MARK_VIEWBOX}>
      {MARK_SEATS.map((seat) => (
        <circle
          key={`${seat.x},${seat.y}`}
          cx={seat.x}
          cy={seat.y}
          r={0.095}
          fill={MARK_FILLS[seat.tone]}
        />
      ))}
    </svg>
  );
}

function Wordmark({ width, color }: { width: number; color: string }) {
  return (
    <svg
      width={width}
      height={Math.round((width * 114) / 880)}
      viewBox={WORDMARK_VIEWBOX}
    >
      {WORDMARK_PATHS.map(({ d, check }) => (
        <path key={d} d={d} fill={check ? CHECK_RED : color} />
      ))}
    </svg>
  );
}

/** The player's own days only: how they did, never how anyone voted. */
function Period({ days, width }: { days: DayRecord[]; width: number }) {
  const seats = periodSeats(days, false);
  return (
    <svg width={width} height={markHeight(width)} viewBox={MARK_VIEWBOX}>
      {seats.map((seat) => {
        const at = {
          cx: seat.x,
          cy: seat.y,
          r: MARK_SEAT_RADIUS,
        };
        const key = `${seat.x},${seat.y}`;
        if (seat.kind === 'played') {
          return <circle key={key} {...at} fill={TIER_FILLS[seat.tier]} />;
        }
        if (seat.kind === 'missed') {
          return (
            <circle
              key={key}
              {...at}
              fill="none"
              stroke={C.muted}
              strokeWidth={0.02}
              strokeDasharray="0.03 0.025"
            />
          );
        }
        return (
          <circle
            key={key}
            {...at}
            fill="none"
            stroke={C.faint}
            strokeWidth={0.018}
          />
        );
      })}
    </svg>
  );
}

/**
 * The image that travels with a shared result: the player's Stimmkarte with
 * an "Abgestimmt" sticker and, on the square and the story, their
 * Wahlperiode. Without a result it is the preview of the plain game link,
 * which asks the game's question and shows no day.
 */
function ShareImage({ format, result }: ShareImageData) {
  const s = SIZES[format];
  const story = format === 'story';
  const days = format === 'link' ? undefined : result?.days;
  const display = { fontFamily: SHARE_FONTS.display, fontWeight: 800 };

  const brand = (
    <div
      style={{
        display: 'flex',
        flexDirection: story ? 'column' : 'row',
        alignItems: 'center',
        gap: story ? 12 : 18,
      }}
    >
      <Mark width={s.mark} />
      <span
        style={{
          ...display,
          fontSize: s.word,
          lineHeight: 1,
          letterSpacing: story ? -5 : -3,
        }}
      >
        Stimmt’s?
      </span>
    </div>
  );

  const card = (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        gap: s.cardGap,
        padding: s.cardPadding,
        borderRadius: 28,
        background: C.ink,
        color: C.paper,
        // The story's card tilts a little.
        ...(story ? { transform: 'rotate(-2deg)' } : {}),
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 14,
          right: 14,
          bottom: 14,
          left: 14,
          border: `2px solid ${C.muted}`,
          borderRadius: 18,
        }}
      />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Wordmark width={s.wordmark} color={C.paper} />
        <span
          style={{
            fontSize: format === 'link' ? 20 : 24,
            fontWeight: 700,
            letterSpacing: 4,
            color: C.muted,
          }}
        >
          STIMMKARTE
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: format === 'link' ? 'center' : 'stretch',
          gap: 40,
        }}
      >
        <div
          style={{
            display: 'flex',
            flex: 1,
            flexDirection: 'column',
            justifyContent: 'center',
          }}
        >
          {result ? (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span
                style={{
                  ...display,
                  fontSize: s.score,
                  lineHeight: 1,
                  letterSpacing: -5,
                }}
              >
                {result.score} von {MAX_SCORE}
              </span>
              <span
                style={{
                  fontSize: s.right,
                  lineHeight: 1.3,
                  fontWeight: 700,
                  color: C.muted,
                }}
              >
                richtig getippt
              </span>
              <Squares score={result.score} size={s.square} top={s.squareGap} />
            </div>
          ) : (
            <span
              style={{
                ...display,
                fontSize: 50,
                lineHeight: 1.12,
                letterSpacing: -1.5,
              }}
            >
              {QUESTION}
            </span>
          )}
        </div>
        {result && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              paddingLeft: 40,
              borderLeft: `3px solid ${C.muted}`,
            }}
          >
            <span style={{ fontSize: 28, color: C.muted }}>Nr.</span>
            <span
              style={{
                ...display,
                fontSize: s.number,
                lineHeight: 1,
                letterSpacing: -3,
              }}
            >
              {result.number}
            </span>
            <span style={{ fontSize: 28, color: C.muted }}>
              {shortDay(result.playDate)}
            </span>
          </div>
        )}
      </div>
      {result && (
        <span
          style={{
            ...display,
            position: 'absolute',
            bottom: format === 'link' ? -22 : -30,
            right: 44,
            padding: '4px 18px',
            border: `6px solid ${C.brandRed}`,
            borderRadius: 12,
            transform: 'rotate(6deg)',
            background: C.paper,
            color: C.brandRed,
            fontSize: s.stamp,
            lineHeight: 1.2,
          }}
        >
          Abgestimmt
        </span>
      )}
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: story ? 'center' : 'space-between',
        gap: story ? 100 : 0,
        width: '100%',
        height: '100%',
        padding: s.padding,
        background: C.paper,
        color: C.ink,
        fontFamily: SHARE_FONTS.sans,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: story ? 'center' : 'flex-start',
        }}
      >
        {brand}
      </div>
      {card}
      {days && (
        <div
          style={{
            display: 'flex',
            flexDirection: story ? 'column' : 'row',
            alignItems: 'center',
            gap: story ? 24 : 40,
          }}
        >
          <Period days={days} width={story ? 520 : 360} />
          <span
            style={{
              ...display,
              fontSize: 56,
              lineHeight: 1.07,
              letterSpacing: -1.5,
            }}
          >
            Tag {days.length} von {PERIOD_LENGTH}
          </span>
        </div>
      )}
      <div
        style={{
          display: 'flex',
          flexDirection: story ? 'column' : 'row',
          justifyContent: 'space-between',
          alignItems: story ? 'center' : 'baseline',
          gap: story ? 8 : 32,
        }}
      >
        <span style={{ ...display, fontSize: s.cta, letterSpacing: -1.5 }}>
          {result ? 'Schaffst du mehr?' : 'Jeden Tag ein neues Rätsel.'}
        </span>
        <span style={{ fontSize: s.url, color: C.muted }}>
          wahl.chat/stimmts
        </span>
      </div>
    </div>
  );
}

/** The score as squares, right answers first, so no party order shows. */
function Squares({
  score,
  size,
  top,
}: {
  score: number;
  size: number;
  top: number;
}) {
  return (
    <div style={{ display: 'flex', gap: 12, marginTop: top }}>
      {Array.from({ length: MAX_SCORE }, (_, i) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed positions.
          key={i}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: size,
            height: size,
            borderRadius: 10,
            ...(i < score
              ? { background: C.correct }
              : { border: `4px solid ${C.muted}` }),
          }}
        >
          {i < score && (
            // Drawn rather than typed: the fonts here have no ✓ glyph.
            <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24">
              <path
                d="M4 12.5l5 5L20 6.5"
                fill="none"
                stroke={C.paper}
                strokeWidth={3.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
      ))}
    </div>
  );
}

export default ShareImage;
