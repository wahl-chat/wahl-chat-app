import type { Context } from '@/lib/firebase/firebase.types';

// Context.date is a Date by the time it reaches a consumer, but the value comes
// out of Firestore, so a hand-seeded string can still arrive. Accept both rather
// than trusting either — this is the one place that does real date arithmetic
// on it.
type ContextDate = Context['date'] | string | undefined;

function toDate(date: ContextDate): Date | undefined {
  if (!date) return undefined;

  const parsed = date instanceof Date ? date : new Date(date);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function startOfDay(date: Date): Date {
  const start = new Date(date);
  start.setHours(0, 0, 0, 0);
  return start;
}

/**
 * A context counts as upcoming while its election is still ahead. Contexts
 * without a date are always upcoming — they are standing topics rather than a
 * dated election.
 *
 * The comparison is against the start of today rather than the current moment,
 * so an election stays upcoming through its own polling day: context dates are
 * midnight, and comparing against the clock would demote an election at 00:01
 * on the morning people are voting in it.
 */
export function isUpcomingElection(
  context: Context,
  now = new Date(),
): boolean {
  const date = toDate(context.date);
  if (!date) return true;

  return date >= startOfDay(now);
}

/**
 * Breaks ties between elections held on the same day, nearest-first.
 *
 * Berlin and Mecklenburg-Vorpommern both vote on 20 September 2026, so the
 * date alone cannot say which one the landing page should lead with — without
 * this the winner is whichever order Firestore happened to return them in,
 * which is not a decision anyone made. Ids listed here sort ahead of any other
 * election sharing their day; everything else keeps the order it arrived in,
 * because Array.prototype.sort is stable.
 *
 * This only ever reorders elections that tie. It cannot promote one past an
 * election that is genuinely sooner.
 */
const SAME_DAY_ORDER = ['landtagswahl-mecklenburg-vorpommern-2026'];

function sameDayRank(context: Context): number {
  const index = SAME_DAY_ORDER.indexOf(context.context_id);
  return index === -1 ? SAME_DAY_ORDER.length : index;
}

function compareByDateAscending(a: Context, b: Context): number {
  const dateA = toDate(a.date);
  const dateB = toDate(b.date);

  // Undated contexts sort last — a concrete election date is the stronger signal.
  if (!dateA && !dateB) return 0;
  if (!dateA) return 1;
  if (!dateB) return -1;

  // Compared by day, not by instant, so two elections on the same date reach
  // the tie-break even if their timestamps differ by hours.
  const dayA = startOfDay(dateA).getTime();
  const dayB = startOfDay(dateB).getTime();
  if (dayA !== dayB) return dayA - dayB;

  return sameDayRank(a) - sameDayRank(b);
}

/**
 * Splits contexts into upcoming (nearest election first) and past.
 */
export function splitElectionsByDate(
  contexts: Context[],
  now = new Date(),
): { upcoming: Context[]; past: Context[] } {
  const upcoming: Context[] = [];
  const past: Context[] = [];

  for (const context of contexts) {
    if (isUpcomingElection(context, now)) {
      upcoming.push(context);
    } else {
      past.push(context);
    }
  }

  return { upcoming: upcoming.sort(compareByDateAscending), past };
}

/**
 * The election to present by default. Undefined when every context is in the
 * past, which callers must handle — it is the steady state between elections.
 */
export function getNextUpcomingElection(
  contexts: Context[],
  now = new Date(),
): Context | undefined {
  return splitElectionsByDate(contexts, now).upcoming[0];
}
