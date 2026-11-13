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
};

/**
 * Everything an image may show. Never the topic, the title or anything per
 * party: like the share text, it must not hint at the day's answers.
 */
export type ShareImageData = {
  format: ShareFormat;
  /** Absent on the preview of the plain game link, which shows no day. */
  result?: SharedResult;
};

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
