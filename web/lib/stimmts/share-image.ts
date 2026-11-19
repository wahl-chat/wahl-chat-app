import { addDays, isIsoDate } from './berlin-time';
import { SEATING_ORDER } from './parties';
import { type DayRecord, PERIOD_LENGTH, encodePeriod } from './period';

/**
 * The share image's sizes. `link` is a link preview: of a shared result, or,
 * without one, of the plain game link.
 */
export const SHARE_FORMATS = {
  square: { width: 1080, height: 1080 },
  story: { width: 1080, height: 1920 },
  link: { width: 1200, height: 630 },
} as const;

type ShareFormat = keyof typeof SHARE_FORMATS;

/**
 * Fixed colours: an image leaves the app, so it must not follow the sharer's
 * theme. The seat colours are the logo's.
 */
export const SHARE_COLORS = {
  ink: '#09090b',
  paper: '#fafafa',
  muted: '#71717a',
  faint: '#d4d4d8',
  correct: '#15803d',
  brandRed: '#ed3833',
  seatYes: '#2f8a5b',
  seatNo: '#c2414b',
  seatAbstain: '#d9a93a',
} as const;

export const MAX_SCORE = SEATING_ORDER.length;

/** One player's day, as a shared result shows it. */
type SharedResult = {
  number: number;
  playDate: string;
  score: number;
  /** The player's period through this day (square and story only). */
  days?: DayRecord[];
  /**
   * The vote's title, looked up on the server from the number. Never read
   * from the URL, or anyone could put their own words on the image.
   */
  title?: string;
};

/**
 * Everything an image may show. The vote's title is public on the start
 * screen and says nothing about the answers, so it may appear; anything per
 * party may not: like the share text, the image must not hint at how anyone
 * voted.
 */
export type ShareImageData = {
  format: ShareFormat;
  /** Absent on the preview of the plain game link, which shows no day. */
  result?: SharedResult;
};

/**
 * The title's sizes, largest first, in the units of the design boards. Each
 * format draws them multiplied by its own scale, so a title breaks into the
 * same lines on every format.
 */
const TITLE_SIZES = [30, 24, 20] as const;

export type ShareTitleSize = (typeof TITLE_SIZES)[number];

const TITLE_MAX_LINES = 3;

/**
 * The width of the title's text box in board units: on the 1080 px square
 * (scale 2.5) that is the card's 800 px inner width. Wide enough for the
 * longest word of any puzzle title so far ("Gebäudemodernisierungsgesetz",
 * about 318 units at size 20) to stay whole.
 */
export const SHARE_TITLE_WIDTH = 320;

/** The title's tracking, in em. */
export const SHARE_TITLE_TRACKING = -0.01;

/**
 * Advance widths in em of Bricolage Grotesque ExtraBold, the title's face,
 * read from the font file. Next/og cannot measure text before drawing it, so
 * the line breaks are estimated from these.
 */
// biome-ignore format: a table reads better packed than one glyph per line.
const TITLE_GLYPH_WIDTHS: Record<string, number> = {
  ' ': 0.22, '(': 0.33, ')': 0.33, '-': 0.36, '0': 0.67, '1': 0.36,
  '2': 0.61, '3': 0.61, '4': 0.64, '5': 0.61, '6': 0.66, '7': 0.52,
  '8': 0.66, '9': 0.66, A: 0.71, B: 0.69, C: 0.69, D: 0.7, E: 0.63, F: 0.6,
  G: 0.73, H: 0.73, I: 0.3, J: 0.38, K: 0.7, L: 0.51, M: 0.95, N: 0.79,
  O: 0.72, P: 0.65, Q: 0.73, R: 0.69, S: 0.66, T: 0.58, U: 0.73, V: 0.68,
  W: 1.0, X: 0.72, Y: 0.66, Z: 0.58, a: 0.59, b: 0.65, c: 0.57, d: 0.65,
  e: 0.59, f: 0.41, g: 0.61, h: 0.64, i: 0.29, j: 0.29, k: 0.6, l: 0.28,
  m: 0.96, n: 0.64, o: 0.61, p: 0.65, q: 0.65, r: 0.45, s: 0.55, t: 0.41,
  u: 0.63, v: 0.58, w: 0.88, x: 0.59, y: 0.61, z: 0.54, Ä: 0.71, Ö: 0.72,
  Ü: 0.73, ß: 0.69, ä: 0.59, ö: 0.61, ü: 0.63, '₂': 0.44,
};

// Wider than any letter above except M, W, m and w, so an unlisted character
// errs towards a smaller size rather than an overflowing line.
const UNKNOWN_GLYPH_WIDTH = 0.75;

function textWidth(text: string, size: number): number {
  let em = 0;
  for (const char of text) {
    em +=
      (TITLE_GLYPH_WIDTHS[char] ?? UNKNOWN_GLYPH_WIDTH) + SHARE_TITLE_TRACKING;
  }
  return em * size;
}

/**
 * How many lines the title breaks into at `size`, breaking between words
 * only, or null if a single word is wider than the box (it would have to
 * break mid-word).
 */
export function shareTitleLines(title: string, size: number): number | null {
  const space = textWidth(' ', size);
  let lines = 0;
  let lineWidth = 0;
  for (const word of title.split(/\s+/).filter(Boolean)) {
    const width = textWidth(word, size);
    if (width > SHARE_TITLE_WIDTH) {
      return null;
    }
    if (lines > 0 && lineWidth + space + width <= SHARE_TITLE_WIDTH) {
      lineWidth += space + width;
    } else {
      lines += 1;
      lineWidth = width;
    }
  }
  return lines;
}

/**
 * The largest size at which the title fits in three lines. The smallest
 * size is the floor: a title too long even for it still draws at it, and the
 * image lets it wrap further rather than shrinking it out of legibility.
 */
export function shareTitleSize(title: string): ShareTitleSize {
  for (const size of TITLE_SIZES) {
    const lines = shareTitleLines(title, size);
    if (lines !== null && lines <= TITLE_MAX_LINES) {
      return size;
    }
  }
  return TITLE_SIZES[TITLE_SIZES.length - 1];
}

// No game ran before 2026. With the upper bound in parseShareParams, this
// keeps junk dates out of the image cache without a year that runs out.
const FIRST_PLAY_DATE = '2026-01-01';

const PERIOD_PATTERN = new RegExp(`^[0-${MAX_SCORE}x]{1,${PERIOD_LENGTH}}$`);

function wholeNumber(value: string | null): number | null {
  return value !== null && /^\d{1,4}$/.test(value) ? Number(value) : null;
}

/** "44x5" (see encodePeriod) back into day records, ending on the shared day. */
function decodePeriod(
  encoded: string,
  { number: lastNumber, playDate: lastDate }: SharedResult,
): DayRecord[] {
  const first = lastNumber - encoded.length + 1;
  return [...encoded].map((mark, index) => {
    const number = first + index;
    const playDate = addDays(lastDate, number - lastNumber);
    return mark === 'x'
      ? { kind: 'missed', number, playDate }
      : { kind: 'played', number, playDate, topic: '', score: Number(mark) };
  });
}

/**
 * Reads and checks a share image request. Every parameter comes from a URL
 * anyone can type, so anything out of range is refused rather than drawn.
 * `f` format, `n` puzzle number, `s` score, `d` the day it was played, `p`
 * the period (see encodePeriod). The link carries its own date, so drawing it
 * needs neither the launch date nor a database. The date may lie up to a run's
 * length after `today`, which preview mode's future days need.
 */
export function parseShareParams(
  params: URLSearchParams,
  puzzleCount: number,
  today: string,
): ShareImageData | null {
  const format = params.get('f') ?? 'square';
  if (!Object.hasOwn(SHARE_FORMATS, format)) {
    return null;
  }
  if (!['n', 's', 'd', 'p'].some((key) => params.has(key))) {
    return format === 'link' ? { format } : null;
  }

  const number = wholeNumber(params.get('n'));
  const score = wholeNumber(params.get('s'));
  const playDate = params.get('d');
  if (
    number === null ||
    number < 1 ||
    number > puzzleCount ||
    score === null ||
    score > MAX_SCORE ||
    !isIsoDate(playDate) ||
    playDate < FIRST_PLAY_DATE ||
    playDate > addDays(today, puzzleCount)
  ) {
    return null;
  }
  const result: SharedResult = { number, playDate, score };

  const period = params.get('p');
  if (period !== null) {
    // The period ends on the shared puzzle's day, so its length is fixed by
    // the number: day 10 of a period is ten characters, the last one played.
    const day = ((number - 1) % PERIOD_LENGTH) + 1;
    if (
      !PERIOD_PATTERN.test(period) ||
      period.length !== day ||
      period.at(-1) !== String(score)
    ) {
      return null;
    }
    result.days = decodePeriod(period, result);
  }
  return { format: format as ShareFormat, result };
}

type ResultParams = Omit<SharedResult, 'days'> & {
  /** encodePeriod's string for the period through this puzzle. */
  period?: string;
};

function resultQuery({ number, score, playDate }: ResultParams) {
  return { n: String(number), s: String(score), d: playDate };
}

/** The path of a share image, relative to the site. */
export function shareImagePath(
  format: ShareFormat,
  result?: ResultParams,
): string {
  const params = new URLSearchParams({
    f: format,
    ...(result && resultQuery(result)),
  });
  if (result?.period !== undefined) {
    params.set('p', result.period);
  }
  return `/stimmts/share?${params}`;
}

/** The link a player shares: the game, with their number, score and day. */
export function sharedResultPath(result: ResultParams): string {
  return `/stimmts?${new URLSearchParams(resultQuery(result))}`;
}

/**
 * The one URL that draws this image. The route redirects every other
 * spelling (parameters in another order, extra or repeated ones) to it, so a
 * cache holds each image once and junk parameters cannot fill it.
 */
export function canonicalSharePath({ format, result }: ShareImageData): string {
  return shareImagePath(
    format,
    result && {
      ...result,
      period: result.days && encodePeriod(result.days),
    },
  );
}
