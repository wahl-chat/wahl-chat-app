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
  SHARE_THEMES,
  SHARE_TITLE_TRACKING,
  SHARE_TITLE_WIDTH,
  type ShareImageData,
  type ShareTheme,
  shareTitleSize,
} from '@/lib/stimmts/share-image';
import type { StyleId } from '@/lib/stimmts/styles';
import type { CSSProperties } from 'react';
import {
  FestiveTree,
  ShareDecor,
  cardFrame,
  decorScale,
  halo,
} from './share-decor';

/** The font families the route registers. */
export const SHARE_FONTS = {
  display: 'Bricolage',
  sans: 'Arimo',
  serif: 'Tinos',
} as const;

const QUESTION = 'Wie haben die Parteien im Bundestag abgestimmt?';

const MARK_FILLS: Record<MarkTone, string> = {
  no: C.seatNo,
  abstain: C.seatAbstain,
  yes: C.seatYes,
};

// Standard's tiers are faint, muted and ink, which its theme names ring, mid
// and top.
const tierFills = (t: ShareTheme): Record<ScoreTier, string> => ({
  low: t.ring,
  mid: t.mid,
  top: t.top,
});

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
  /** Top and bottom, then left and right. */
  padding: [number, number];
  /** Multiplies the title's sizes in base units (see shareTitleSize). */
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
    padding: [64, 72],
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
    padding: [140, 72],
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
    padding: [40, 56],
    titleScale: 2,
    logo: 64,
    mark: 76,
    word: 40,
    cardPadding: '26px 40px 46px',
    cardGap: 16,
    label: 20,
    score: 40,
    right: 26,
    square: 36,
    stamp: 32,
    cta: 38,
    url: 28,
  },
};

const DISPLAY = { fontFamily: SHARE_FONTS.display, fontWeight: 800 };

/** The headline face: Papier sets its headlines in a serif. */
const headline = (t: ShareTheme): CSSProperties =>
  t.serif ? { fontFamily: SHARE_FONTS.serif, fontWeight: 700 } : DISPLAY;

/** The wahl.chat logo, the same artwork as in the site header. */
function WahlChatLogo({ height, ink }: { height: number; ink: string }) {
  return (
    <svg width={logoWidth(height)} height={height} viewBox={LOGO_VIEWBOX}>
      {LOGO_PATHS.map(({ d, check }) => (
        <path key={d} d={d} fill={check ? CHECK_RED : ink} />
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
function Period({
  days,
  width,
  t,
}: {
  days: DayRecord[];
  width: number;
  t: ShareTheme;
}) {
  const seats = periodSeats(days, false);
  const fills = tierFills(t);
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
          return <circle key={key} {...at} fill={fills[seat.tier]} />;
        }
        if (seat.kind === 'missed') {
          return (
            <circle
              key={key}
              {...at}
              fill="none"
              stroke={t.mid}
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
            stroke={t.ring}
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
function Title({
  title,
  scale,
  t,
}: {
  title: string;
  scale: number;
  t: ShareTheme;
}) {
  const fontSize = shareTitleSize(title) * scale;
  return (
    <span
      style={{
        ...headline(t),
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
function Squares({
  score,
  size,
  t,
}: {
  score: number;
  size: number;
  t: ShareTheme;
}) {
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
              ? { background: t.correct }
              : { border: `4px solid ${t.mid}` }),
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

type CardPart = { result: Result; s: Sizes; t: ShareTheme };

/** Square and story: the score in one line under the title. */
function ScoreLine({ result, s, t }: CardPart) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
      <Squares score={result.score} size={s.square} t={t} />
      <span style={{ fontSize: s.score, fontWeight: 700 }}>
        {result.score} von {MAX_SCORE}
      </span>
      <span style={{ fontSize: s.right, color: t.mid }}>richtig getippt</span>
    </div>
  );
}

/**
 * The link preview is wide and low: the score stands beside the title, in
 * the plain face and smaller, so the title stays the main text. The squares
 * come first, keeping them clear of the stamp at the card's lower edge.
 */
function ScoreColumn({ result, s, t }: CardPart) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        gap: 12,
        paddingLeft: 36,
        borderLeft: `3px solid ${t.mid}`,
      }}
    >
      <Squares score={result.score} size={s.square} t={t} />
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontSize: s.score, fontWeight: 700, lineHeight: 1.1 }}>
          {result.score} von {MAX_SCORE}
        </span>
        <span style={{ fontSize: s.right, color: t.mid }}>richtig getippt</span>
      </div>
    </div>
  );
}

function Card({
  format,
  result,
  style,
  t,
}: Pick<ShareImageData, 'format' | 'result'> & {
  style: StyleId;
  t: ShareTheme;
}) {
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
        background: t.card,
        color: t.cardText,
        // The story's card tilts a little.
        ...(format === 'story' ? { transform: 'rotate(-2deg)' } : {}),
        ...cardFrame(style, t, decorScale(format)),
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 14,
          right: 14,
          bottom: 14,
          left: 14,
          border: `2px solid ${t.mid}`,
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
          color: t.mid,
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
          <Title title={result.title ?? QUESTION} scale={s.titleScale} t={t} />
          {link ? (
            <ScoreColumn result={result} s={s} t={t} />
          ) : (
            <ScoreLine result={result} s={s} t={t} />
          )}
        </div>
      ) : (
        <span
          style={{
            ...headline(t),
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
function ShareImage({ format, result, style = 'standard' }: ShareImageData) {
  const s = SIZES[format];
  const story = format === 'story';
  const days = format === 'link' ? undefined : result?.days;
  // The plain game link has no sharer, so it never wears a style.
  const styleId = result ? style : 'standard';
  const t = SHARE_THEMES[styleId];
  const k = decorScale(format);
  const [padY, padX] = s.padding;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: story ? 'center' : 'space-between',
        gap: story ? 100 : 0,
        width: '100%',
        height: '100%',
        padding: `${padY}px ${padX}px`,
        // Room for the decorations some styles draw along the edges.
        ...(t.topOffset ? { paddingTop: padY + t.topOffset * k } : {}),
        ...(t.bottomOffset ? { paddingBottom: padY + t.bottomOffset * k } : {}),
        background: t.canvas,
        color: t.ink,
        fontFamily: SHARE_FONTS.sans,
      }}
    >
      <ShareDecor style={styleId} format={format} theme={t} />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        {styleId === 'kuppel' ? (
          <div style={{ display: 'flex', ...halo(styleId, t, k) }}>
            <WahlChatLogo height={s.logo} ink={t.ink} />
          </div>
        ) : (
          <WahlChatLogo height={s.logo} ink={t.ink} />
        )}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            ...halo(styleId, t, k),
          }}
        >
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
      <Card format={format} result={result} style={styleId} t={t} />
      {days && (
        <div
          style={{
            display: 'flex',
            flexDirection: story ? 'column' : 'row',
            alignItems: 'center',
            gap: story ? 24 : 40,
          }}
        >
          <Period days={days} width={story ? 480 : 280} t={t} />
          <span
            style={{
              ...headline(t),
              fontSize: 48,
              lineHeight: 1.07,
              letterSpacing: -1.5,
            }}
          >
            Tag {days.length} von {PERIOD_LENGTH}
          </span>
          {styleId === 'festlich' && !story && (
            <div style={{ display: 'flex', marginLeft: 'auto' }}>
              <FestiveTree width={130} />
            </div>
          )}
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
        <span style={{ ...headline(t), fontSize: s.cta, letterSpacing: -1.5 }}>
          {result
            ? shareInvitation({ correct: result.score, total: MAX_SCORE })
            : 'Jeden Tag ein neues Quiz.'}
        </span>
        <span
          style={{ fontSize: s.url, color: t.muted, ...halo(styleId, t, k) }}
        >
          wahl.chat/stimmts
        </span>
      </div>
    </div>
  );
}

export default ShareImage;
