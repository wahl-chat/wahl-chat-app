import type {
  DailyDigest,
  DigestParliamentId,
} from '@/lib/firebase/firebase.types';

export const FEED_WINDOW_DAYS = 14;

const PARLIAMENT_ORDER: DigestParliamentId[] = [
  'bundestag',
  'landtag_st',
  'landtag_bw',
];

export type FeedDay = {
  date: string;
  digests: DailyDigest[];
};

function shiftDay(isoDay: string, days: number): string {
  const date = new Date(`${isoDay}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/**
 * Each parliament's window ends on ITS latest digest, not today: Landtage sit
 * irregularly, and a fixed calendar window would show an empty state for a
 * parliament that simply has not met for a while.
 */
export function windowedDigests(
  digests: readonly DailyDigest[],
  windowDays: number = FEED_WINDOW_DAYS,
): DailyDigest[] {
  if (digests.length === 0) {
    return [];
  }
  const latest = digests.reduce(
    (max, d) => (d.date > max ? d.date : max),
    digests[0].date,
  );
  const earliest = shiftDay(latest, -(windowDays - 1));
  return digests.filter((d) => d.date >= earliest);
}

/** Merge per-parliament digests into days, newest first; Bundestag first. */
export function buildFeed(
  perParliament: readonly (readonly DailyDigest[])[],
  windowDays: number = FEED_WINDOW_DAYS,
): FeedDay[] {
  const byDate = new Map<string, DailyDigest[]>();
  for (const digests of perParliament) {
    for (const digest of windowedDigests(digests, windowDays)) {
      const day = byDate.get(digest.date) ?? [];
      day.push(digest);
      byDate.set(digest.date, day);
    }
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, digests]) => ({
      date,
      digests: digests.sort(
        (a, b) =>
          PARLIAMENT_ORDER.indexOf(a.parliament) -
          PARLIAMENT_ORDER.indexOf(b.parliament),
      ),
    }));
}

export function formatFeedDay(isoDay: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${isoDay}T00:00:00Z`));
}
