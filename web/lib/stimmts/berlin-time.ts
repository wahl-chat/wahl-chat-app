// Everyone plays the same puzzle on the same day, so "today" is always the
// calendar date in Berlin, whatever the player's own clock or timezone says.
const TIME_ZONE = 'Europe/Berlin';

const MS_PER_HOUR = 3_600_000;
const MS_PER_DAY = 24 * MS_PER_HOUR;
// The longest Berlin day is 25 hours (clocks go back in October).
const LONGEST_DAY_MS = 25 * MS_PER_HOUR;

const dayFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

/** The calendar date in Berlin at the given moment, as YYYY-MM-DD. */
export function berlinDate(now: Date): string {
  const parts = dayFormatter.formatToParts(now);
  const part = (type: string) =>
    parts.find((entry) => entry.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}

/**
 * Whether the value is a real calendar date written as YYYY-MM-DD. The
 * round trip through Date rejects impossible days such as 2026-02-31, which
 * some JavaScript engines would otherwise quietly roll over into March.
 */
export function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = Date.parse(value);
  return (
    !Number.isNaN(parsed) &&
    new Date(parsed).toISOString().slice(0, 10) === value
  );
}

// Dates are plain YYYY-MM-DD strings, so counting days between them is done
// at UTC midnight, where a day is always exactly 24 hours (no daylight-saving
// surprises).
function toUtcMs(date: string): number {
  const [year, month, day] = date.split('-').map(Number);
  return Date.UTC(year, month - 1, day);
}

/** Whole days from one YYYY-MM-DD date to another (negative if earlier). */
export function daysBetween(from: string, to: string): number {
  return (toUtcMs(to) - toUtcMs(from)) / MS_PER_DAY;
}

export function addDays(date: string, days: number): string {
  return new Date(toUtcMs(date) + days * MS_PER_DAY).toISOString().slice(0, 10);
}

/**
 * The first moment of the next Berlin day, i.e. when tomorrow's puzzle opens.
 *
 * Found by bisection instead of arithmetic: the Berlin date only ever moves
 * forward, so we narrow down the instant it changes. That stays correct on the
 * two days a year that are 23 or 25 hours long, which "24 hours minus the time
 * so far" would get wrong.
 */
export function nextPuzzleAt(now: Date): Date {
  const today = berlinDate(now);
  let stillToday = now.getTime();
  let nextDay = stillToday + LONGEST_DAY_MS;
  while (nextDay - stillToday > 1) {
    const middle = Math.floor((stillToday + nextDay) / 2);
    if (berlinDate(new Date(middle)) === today) {
      stillToday = middle;
    } else {
      nextDay = middle;
    }
  }
  return new Date(nextDay);
}
