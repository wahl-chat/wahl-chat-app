import type { Context } from '@/lib/firebase/firebase.types';

// An election stays "upcoming" for a few days past its date: results are the
// most-searched thing immediately after polls close, so demoting the context on
// election night would be wrong.
const PAST_ELECTION_BUFFER_DAYS = 5;

// Context.date is declared `string | null` but firebase-server.ts maps it
// through firestoreTimestampToDate(), so it is a Date at runtime. Accept both
// rather than trusting either — this is the one place that does real date
// arithmetic on it.
type ContextDate = Context['date'] | Date | undefined;

function toDate(date: ContextDate): Date | undefined {
  if (!date) return undefined;

  const parsed = date instanceof Date ? date : new Date(date);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed;
}

function bufferCutoff(now: Date): Date {
  return new Date(
    now.getTime() - PAST_ELECTION_BUFFER_DAYS * 24 * 60 * 60 * 1000,
  );
}

/**
 * A context counts as upcoming while its election is still ahead (plus the
 * buffer). Contexts without a date are always upcoming — they are standing
 * topics rather than a dated election.
 */
export function isUpcomingElection(
  context: Context,
  now = new Date(),
): boolean {
  const date = toDate(context.date);
  if (!date) return true;

  return date >= bufferCutoff(now);
}

function compareByDateAscending(a: Context, b: Context): number {
  const dateA = toDate(a.date);
  const dateB = toDate(b.date);

  // Undated contexts sort last — a concrete election date is the stronger signal.
  if (!dateA && !dateB) return 0;
  if (!dateA) return 1;
  if (!dateB) return -1;

  return dateA.getTime() - dateB.getTime();
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
