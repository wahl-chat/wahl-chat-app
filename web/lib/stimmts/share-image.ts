import { addDays } from './berlin-time';
import { SEATING_ORDER } from './parties';
import { type DayRecord, PERIOD_LENGTH } from './period';
import type { Schedule } from './types';

/**
 * The share image's sizes. `link` without a score is the preview of the plain
 * game link; with one, of a shared result.
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

/**
 * Everything an image may show. Never the topic, the title or anything per
 * party: like the share text, it must not hint at the day's answers.
 */
export type ShareImageData = {
  format: ShareFormat;
  number: number;
  playDate: string;
  /** Absent for the plain game link. */
  score?: number;
  /** The player's period so far (square and story only). */
  days?: DayRecord[];
};

const PERIOD_PATTERN = new RegExp(`^[0-${MAX_SCORE}x]{1,${PERIOD_LENGTH}}$`);

function wholeNumber(value: string | null): number | null {
  return value !== null && /^\d{1,4}$/.test(value) ? Number(value) : null;
}

/** "44x5" (see encodePeriod) back into day records, from the period's day 1. */
function decodePeriod(
  encoded: string,
  firstNumber: number,
  startDate: string,
): DayRecord[] {
  return [...encoded].map((mark, index) => {
    const number = firstNumber + index;
    const playDate = addDays(startDate, number - 1);
    return mark === 'x'
      ? { kind: 'missed', number, playDate }
      : { kind: 'played', number, playDate, topic: '', score: Number(mark) };
  });
}

/**
 * Reads and checks a share image request. Every parameter comes from a URL
 * anyone can type, so anything out of range is refused rather than drawn.
 * `f` format, `n` puzzle number, `s` score, `p` the period (see encodePeriod).
 */
export function parseShareParams(
  params: URLSearchParams,
  schedule: Schedule,
): ShareImageData | null {
  const format = params.get('f') ?? 'square';
  if (!(format in SHARE_FORMATS)) {
    return null;
  }
  const number = wholeNumber(params.get('n'));
  if (number === null || number < 1 || number > schedule.puzzleIds.length) {
    return null;
  }
  const data: ShareImageData = {
    format: format as ShareFormat,
    number,
    playDate: addDays(schedule.startDate, number - 1),
  };

  const rawScore = params.get('s');
  if (rawScore !== null) {
    const score = wholeNumber(rawScore);
    if (score === null || score > MAX_SCORE) {
      return null;
    }
    data.score = score;
  }

  const period = params.get('p');
  if (period !== null) {
    // The period ends on the shared puzzle's day, so its length is fixed by
    // the number: day 10 of a period is ten characters, the last one played.
    const day = ((number - 1) % PERIOD_LENGTH) + 1;
    if (
      data.score === undefined ||
      !PERIOD_PATTERN.test(period) ||
      period.length !== day ||
      period.at(-1) !== String(data.score)
    ) {
      return null;
    }
    data.days = decodePeriod(period, number - day + 1, schedule.startDate);
  }
  return data;
}

type UrlInput = {
  format: ShareFormat;
  number: number;
  score?: number;
  /** encodePeriod's string for the period through this puzzle. */
  period?: string;
};

/** The path of a share image, relative to the site. */
export function shareImagePath({
  format,
  number,
  score,
  period,
}: UrlInput): string {
  const params = new URLSearchParams({ f: format, n: String(number) });
  if (score !== undefined) {
    params.set('s', String(score));
  }
  if (period !== undefined && score !== undefined) {
    params.set('p', period);
  }
  return `/stimmts/share?${params}`;
}

/** The link a player shares: the game, with their number and score. */
export function sharedResultPath(number: number, score: number): string {
  return `/stimmts?${new URLSearchParams({ n: String(number), s: String(score) })}`;
}
