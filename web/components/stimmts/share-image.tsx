// Rendered to PNG by next/og, not in the browser: only flexbox, absolute
// positioning, inline SVG and fixed colours work there, and every element
// with more than one child needs `display: flex`.

import { CHECK_RED, LOGO_PATHS, LOGO_VIEWBOX } from '@/components/chat/logo';
import { PUZZLES } from '@/lib/stimmts/content';
import { WEEKDAYS, shortDay } from '@/lib/stimmts/labels';
import {
  MARK_SEATS,
  MARK_SEAT_RADIUS,
  MARK_VIEWBOX,
  type MarkTone,
  type ScoreTier,
  periodSeats,
} from '@/lib/stimmts/logo';
import { type DayRecord, PERIOD_LENGTH } from '@/lib/stimmts/period';
import { shareInvitation } from '@/lib/stimmts/share';
import {
  SHARE_COLORS as C,
  MAX_SCORE,
  SHARE_TITLE_TRACKING,
  SHARE_TITLE_WIDTH,
  type ShareImageData,
  shareTitleSize,
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

// The logo's viewBox is 368 wide and 201 high.
const logoWidth = (height: number) => Math.round((height * 368) / 201);

/**
 * Every character any image can show, once each, to cut the fonts down to.
 * The same for every image (all weekdays, all digits, every puzzle title), so
 * one set of fonts serves them all.
 */
export const SHARE_IMAGE_TEXT = [
  ...new Set(
    [
      "Stimmt's?’ STIMMKARTE Nr. · von richtig getippt Abgestimmt Tag",
      `${shareInvitation({ correct: 0, total: MAX_SCORE })} ${shareInvitation({ correct: MAX_SCORE, total: MAX_SCORE })}`,
      'Jeden Tag ein neues Quiz. wahl.chat/stimmts',
      QUESTION,
      WEEKDAYS.map((day) => day.slice(0, 2)).join(' '),
      '0123456789 .',
      ...PUZZLES.map((puzzle) => puzzle.title),
    ].join(''),
  ),
].join('');

type Sizes = {
  padding: string;
  /** Multiplies the title's board sizes (see shareTitleSize). */
  titleScale: number;
  logo: number;
  mark: number;
  word: number;
  cardPadding: string;
  cardGap: number;
  label: number;
  score: number;
  right: number;
  square: number;
  stamp: number;
  cta: number;
  url: number;
};

const SIZES: Record<ShareImageData['format'], Sizes> = {
  square: {
    padding: '64px 72px',
    titleScale: 2.5,
    logo: 92,
    mark: 110,
    word: 56,
    cardPadding: '40px 56px 48px',
    cardGap: 26,
    label: 24,
    score: 40,
    right: 34,
    square: 44,
    stamp: 40,
    cta: 50,
    url: 32,
  },
  story: {
    padding: '140px 72px',
    titleScale: 2.5,
    logo: 120,
    mark: 140,
    word: 70,
    cardPadding: '40px 56px 48px',
    cardGap: 26,
    label: 24,
    score: 40,
    right: 34,
    square: 44,
    stamp: 40,
    cta: 64,
    url: 32,
  },
  link: {
    padding: '40px 56px',
    titleScale: 2,
    logo: 64,
    mark: 76,
    word: 40,
    cardPadding: '26px 40px 46px',
    cardGap: 16,
    label: 20,
    score: 72,
    right: 26,
    square: 36,
    stamp: 32,
    cta: 38,
    url: 28,
  },
};

const DISPLAY = { fontFamily: SHARE_FONTS.display, fontWeight: 800 };

/** The wahl.chat logo, the same artwork as in the site header. */
function WahlChatLogo({ height }: { height: number }) {
  return (
    <svg width={logoWidth(height)} height={height} viewBox={LOGO_VIEWBOX}>
      {LOGO_PATHS.map(({ d, check }) => (
        <path key={d} d={d} fill={check ? CHECK_RED : C.ink} />
      ))}
    </svg>
  );
}

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
 * The vote's title, at the largest size that keeps it to three lines. The
 * box has the width shareTitleSize measured against, so the lines break
 * where it expected.
 */
function Title({ title, scale }: { title: string; scale: number }) {
  const fontSize = shareTitleSize(title) * scale;
  return (
    <span
      style={{
        ...DISPLAY,
        width: SHARE_TITLE_WIDTH * scale,
        fontSize,
        lineHeight: 1.1,
        letterSpacing: SHARE_TITLE_TRACKING * fontSize,
        // Only a title longer than any so far needs this, rather than
        // running off the card.
        wordBreak: 'break-word',
      }}
    >
      {title}
    </span>
  );
}

/** The score as squares, right answers first, so no party order shows. */
function Squares({ score, size }: { score: number; size: number }) {
  return (
    <div style={{ display: 'flex', gap: Math.round(size / 4) }}>
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
            borderRadius: Math.round(size / 5),
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

type Result = NonNullable<ShareImageData['result']>;

/** Square and story: the score in one line under the title. */
function ScoreLine({ result, s }: { result: Result; s: Sizes }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
      <Squares score={result.score} size={s.square} />
      <span style={{ fontSize: s.score, fontWeight: 700 }}>
        {result.score} von {MAX_SCORE}
      </span>
      <span style={{ fontSize: s.right, color: C.muted }}>richtig getippt</span>
    </div>
  );
}

/** The link preview is wide and low: the score stands beside the title. */
function ScoreColumn({ result, s }: { result: Result; s: Sizes }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 10,
        paddingLeft: 36,
        borderLeft: `3px solid ${C.muted}`,
      }}
    >
      <span
        style={{
          ...DISPLAY,
          fontSize: s.score,
          lineHeight: 1,
          letterSpacing: -2,
        }}
      >
        {result.score} von {MAX_SCORE}
      </span>
      <span style={{ fontSize: s.right, fontWeight: 700, color: C.muted }}>
        richtig getippt
      </span>
      <Squares score={result.score} size={s.square} />
    </div>
  );
}

function Card({ format, result }: Pick<ShareImageData, 'format' | 'result'>) {
  const s = SIZES[format];
  const link = format === 'link';
  return (
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
        ...(format === 'story' ? { transform: 'rotate(-2deg)' } : {}),
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
          fontSize: s.label,
          fontWeight: 700,
          letterSpacing: 4,
          color: C.muted,
        }}
      >
        <span>STIMMKARTE</span>
        {result && (
          <span style={{ letterSpacing: 0 }}>
            Nr. {result.number} · {shortDay(result.playDate)}
          </span>
        )}
      </div>
      {result ? (
        <div
          style={{
            display: 'flex',
            flexDirection: link ? 'row' : 'column',
            alignItems: link ? 'center' : 'flex-start',
            gap: link ? 36 : 32,
          }}
        >
          <Title title={result.title ?? QUESTION} scale={s.titleScale} />
          {link ? (
            <ScoreColumn result={result} s={s} />
          ) : (
            <ScoreLine result={result} s={s} />
          )}
        </div>
      ) : (
        <span
          style={{
            ...DISPLAY,
            fontSize: 50,
            lineHeight: 1.12,
            letterSpacing: -1.5,
          }}
        >
          {QUESTION}
        </span>
      )}
      {result && (
        <span
          style={{
            ...DISPLAY,
            position: 'absolute',
            bottom: link ? -20 : -28,
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
}

/**
 * The image that travels with a shared result: the wahl.chat logo, the
 * player's Stimmkarte naming the day's vote, with their score and an
 * "Abgestimmt" sticker and, on the square and the story, their Wahlperiode.
 * Without a result it is the preview of the plain game link, which asks the
 * game's question and shows no day.
 */
function ShareImage({ format, result }: ShareImageData) {
  const s = SIZES[format];
  const story = format === 'story';
  const days = format === 'link' ? undefined : result?.days;

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
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <WahlChatLogo height={s.logo} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <Mark width={s.mark} />
          <span
            style={{
              ...DISPLAY,
              fontSize: s.word,
              lineHeight: 1,
              letterSpacing: -2,
            }}
          >
            Stimmt’s?
          </span>
        </div>
      </div>
      <Card format={format} result={result} />
      {days && (
        <div
          style={{
            display: 'flex',
            flexDirection: story ? 'column' : 'row',
            alignItems: 'center',
            gap: story ? 24 : 40,
          }}
        >
          <Period days={days} width={story ? 480 : 280} />
          <span
            style={{
              ...DISPLAY,
              fontSize: 48,
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
        <span style={{ ...DISPLAY, fontSize: s.cta, letterSpacing: -1.5 }}>
          {result
            ? shareInvitation({ correct: result.score, total: MAX_SCORE })
            : 'Jeden Tag ein neues Quiz.'}
        </span>
        <span style={{ fontSize: s.url, color: C.muted }}>
          wahl.chat/stimmts
        </span>
      </div>
    </div>
  );
}

export default ShareImage;
