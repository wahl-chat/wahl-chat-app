import { addDays, berlinDate, calendarDay, daysBetween } from './berlin-time';

type PreviewEnv = {
  vercelEnv?: string;
  nodeEnv?: string;
  flag?: string;
};

/**
 * Preview mode lets us play any day's puzzle before the game is live. It is
 * on while developing and wherever NEXT_PUBLIC_STIMMTS_PREVIEW=true (a test
 * deployment), and never on Vercel's production deployment, whatever the
 * flag says. Decided on the server: VERCEL_ENV never reaches the browser.
 */
export function isPreviewEnabled({
  vercelEnv,
  nodeEnv,
  flag,
}: PreviewEnv): boolean {
  return (
    vercelEnv !== 'production' && (nodeEnv === 'development' || flag === 'true')
  );
}

export type Clock = {
  /** The moment the game treats as "now". */
  now: Date;
};

type ClockOptions = {
  previewEnabled: boolean;
  /** The page's query string, e.g. "?day=3". */
  search: string;
  launchDate: string;
  puzzleCount: number;
  now: Date;
};

/**
 * The clock the game runs on. Normally the real one; in preview mode `?day=N`
 * jumps to the N-th day after the launch date, and without it the game shows
 * today's puzzle (or day 1 before the launch, so there is always something to
 * see). The day after the last puzzle is as far as it goes.
 */
export function resolveClock({
  previewEnabled,
  search,
  launchDate,
  puzzleCount,
  now,
}: ClockOptions): Clock {
  if (!previewEnabled) {
    return { now };
  }

  const requested = Number(new URLSearchParams(search).get('day'));
  const today = daysBetween(launchDate, berlinDate(now)) + 1;
  const day =
    Number.isInteger(requested) && requested >= 1
      ? Math.min(requested, puzzleCount + 1)
      : Math.max(1, today);

  return { now: calendarDay(addDays(launchDate, day - 1)) };
}
