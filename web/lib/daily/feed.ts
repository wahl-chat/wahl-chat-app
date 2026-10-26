import type {
  DailyDigest,
  DigestParliamentId,
} from '@/lib/firebase/firebase.types';
import {
  type SectionItem,
  type VoteItem,
  sectionItems,
  sectionTopics,
  voteItems,
} from './items';
import { matchesTopics } from './topics';

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

/**
 * The per-parliament lists for `buildFeed`, with preview digests as a list of
 * their own: windowed together with the real ones, a preview day weeks ahead
 * of the stored digests would push them all out of the window. A preview
 * replaces the stored digest with the same id.
 */
export function feedLists(
  digests: Record<DigestParliamentId, readonly DailyDigest[]>,
  parliaments: readonly DigestParliamentId[],
  preview: readonly DailyDigest[] = [],
): DailyDigest[][] {
  const shown = preview.filter((d) => parliaments.includes(d.parliament));
  const replaced = new Set(shown.map((d) => d.id));
  const lists = parliaments.map((p) =>
    digests[p].filter((d) => !replaced.has(d.id)),
  );
  return shown.length > 0 ? [...lists, shown] : lists;
}

export type RankedDigest = {
  digest: DailyDigest;
  sections: SectionItem[];
  votes: VoteItem[];
};

export type RankedDay = {
  date: string;
  /** The day's most heated debate, across every parliament shown. */
  hot: SectionItem | null;
  /** A vote on the hot debate's topic: from the same day, else the latest
   * earlier one. A same-day match is left out of `blocks`. */
  match: VoteItem | null;
  /** Everything else, per parliament, debates sorted by prior. */
  blocks: RankedDigest[];
  /** Day-relative heat (1–5) per section key. */
  heat: Map<string, number>;
};

/**
 * The builder rates heat only against the other sections of the same
 * protocol, so the scale differs between sittings and parliaments. Rescaling
 * against the day's hottest section keeps the comparison relative to what the
 * reader sees that day: the hottest always shows 5.
 */
export function dayHeat(sections: readonly SectionItem[]): Map<string, number> {
  const max = Math.max(0, ...sections.map((s) => s.section.heat ?? 0));
  const heat = new Map<string, number>();
  if (max === 0) {
    return heat;
  }
  for (const item of sections) {
    if (item.section.heat) {
      heat.set(
        item.key,
        Math.max(1, Math.round((item.section.heat / max) * 5)),
      );
    }
  }
  return heat;
}

function prior(item: SectionItem, heat: Map<string, number>): number {
  return (item.section.debate_minutes ?? 1) * (heat.get(item.key) ?? 1);
}

/**
 * Each day leads with its own most heated debate and a vote on the same
 * topic, then the rest of that day per parliament. Ranking never crosses
 * days, so a heated debate from last week cannot bury today's.
 */
export function rankFeed(
  days: readonly FeedDay[],
  topics: readonly string[],
): RankedDay[] {
  const visibleVotes = (digest: DailyDigest) =>
    voteItems(digest).filter((v) => matchesTopics(v.vote.topics, topics));

  return days.map((day, dayIndex) => {
    const sections = day.digests.flatMap((digest) =>
      sectionItems(digest).filter((s) =>
        matchesTopics(sectionTopics(s.section), topics),
      ),
    );
    const heat = dayHeat(sections);
    // Stable sort: ties keep stored order (Bundestag first, protocol order).
    const ranked = [...sections].sort(
      (a, b) => prior(b, heat) - prior(a, heat),
    );
    const hot = ranked[0] ?? null;

    const sharesTopic = (v: VoteItem) =>
      hot !== null && v.vote.topics.includes(hot.section.topic);
    const sameDay = day.digests.flatMap(visibleVotes).find(sharesTopic);
    const match =
      sameDay ??
      days
        .slice(dayIndex + 1)
        .flatMap((d) => d.digests.flatMap(visibleVotes))
        .find(sharesTopic) ??
      null;

    const blocks = day.digests
      .map((digest) => ({
        digest,
        sections: ranked.filter(
          (s) => s.digest.id === digest.id && s.key !== hot?.key,
        ),
        votes: visibleVotes(digest).filter((v) => v.key !== sameDay?.key),
      }))
      .filter((b) => b.sections.length > 0 || b.votes.length > 0);

    return { date: day.date, hot, match, blocks, heat };
  });
}
