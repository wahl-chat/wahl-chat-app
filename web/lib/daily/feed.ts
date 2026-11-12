import type {
  DailyDigest,
  DigestParliamentId,
} from '@/lib/firebase/firebase.types';
import { type FeedFilter, showsKind } from './filter';
import {
  type SectionItem,
  type VoteItem,
  sectionItems,
  sectionTopics,
  voteItems,
} from './items';
import { matchesTopics } from './topics';
import { FEED_WINDOW_DAYS, pageStart } from './window';

export { FEED_WINDOW_DAYS };

const PARLIAMENT_ORDER: DigestParliamentId[] = [
  'bundestag',
  'landtag_st',
  'landtag_bw',
];

export type FeedDay = {
  date: string;
  digests: DailyDigest[];
};

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
  const earliest = pageStart(latest, windowDays);
  return digests.filter((d) => d.date >= earliest);
}

/** Merge per-parliament digests into days, newest first; Bundestag first.
 * `windowDays: null` keeps every digest, for lists the server already cut. */
export function buildFeed(
  perParliament: readonly (readonly DailyDigest[])[],
  windowDays: number | null = FEED_WINDOW_DAYS,
): FeedDay[] {
  const byDate = new Map<string, DailyDigest[]>();
  for (const digests of perParliament) {
    const shown =
      windowDays === null ? digests : windowedDigests(digests, windowDays);
    for (const digest of shown) {
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

/** A sitting day stored before any of its items: its debates wait for a
 * readable protocol, its votes for abgeordnetenwatch. */
export function isWaitingDigest(digest: DailyDigest): boolean {
  return sectionItems(digest).length === 0 && voteItems(digest).length === 0;
}

/** A day whose every digest waits. The parliament field announces it; the
 * feed leaves it out. Decided before any topic filter, so a day the filter
 * empties is never one. */
export function isPendingDay(day: FeedDay): boolean {
  return day.digests.every(isWaitingDigest);
}

export type RankedDigest = {
  digest: DailyDigest;
  sections: SectionItem[];
  votes: VoteItem[];
};

export type RankedDay = {
  date: string;
  /** The day's most heated debate, across every parliament shown: the most
   * interjections per minute. */
  hot: SectionItem | null;
  /** The day's vote on the hot debate's agenda item, if there was one. Left
   * out of `blocks`, so it is not shown twice. */
  match: VoteItem | null;
  /** Everything else, per parliament, debates most heated first. */
  blocks: RankedDigest[];
  /** Day-relative heat (1–5 flames) per section key. */
  heat: Map<string, number>;
};

/** Interjections per minute of debate; null when not counted. */
function interjectionRate(item: SectionItem): number | null {
  const { interjections, debate_minutes } = item.section;
  if (interjections == null || !debate_minutes) {
    return null;
  }
  return interjections / debate_minutes;
}

export const HEAT_SCALE = 5;

/** What the flames count, then what this debate's number of them says; the
 * flames themselves stand in front of that second part. The scale is
 * relative to the day, so it names the day. */
export function heatExplanation(heat: number): [string, string] {
  const counted =
    'Die Flammen zählen Zwischenrufe, Widerspruch, Gelächter und Unruhe.';
  if (heat >= HEAT_SCALE) {
    return [counted, 'die hitzigste Debatte dieses Sitzungstags'];
  }
  if (heat <= 1) {
    return [counted, 'die ruhigste Debatte dieses Sitzungstags'];
  }
  return [counted, 'verglichen mit den anderen Debatten dieses Sitzungstags'];
}

/**
 * Heat compares a day's debates with each other, never with a fixed scale:
 * interjections per minute, counted from the protocol, spread from 1 flame
 * for the day's quietest debate to 5 for its busiest. With fewer than two
 * counted debates, or none that differ, there is nothing to compare and no
 * debate gets flames.
 */
export function dayHeat(sections: readonly SectionItem[]): Map<string, number> {
  const rated = sections.flatMap((item) => {
    const rate = interjectionRate(item);
    return rate === null ? [] : [{ key: item.key, rate }];
  });
  const heat = new Map<string, number>();
  const min = Math.min(...rated.map((r) => r.rate));
  const max = Math.max(...rated.map((r) => r.rate));
  if (rated.length < 2 || max === min) {
    return heat;
  }
  for (const { key, rate } of rated) {
    heat.set(
      key,
      1 + Math.round(((HEAT_SCALE - 1) * (rate - min)) / (max - min)),
    );
  }
  return heat;
}

/**
 * Each day leads with its own most heated debate and the vote on it, then the
 * rest of that day per parliament. Ranking never crosses days, so a heated
 * debate from last week cannot bury today's.
 *
 * The vote must share a Drucksache with the debate's agenda item: that is the
 * motion debated. A shared topic is not enough.
 *
 * The filter applies before ranking: with debates left out there is no Hot
 * Topic and no heat; with votes left out, no vote under the Hot Topic.
 */
export function rankFeed(
  days: readonly FeedDay[],
  filter: FeedFilter,
): RankedDay[] {
  const { topics } = filter;
  const visibleVotes = (digest: DailyDigest) =>
    showsKind(filter, 'vote')
      ? voteItems(digest).filter((v) => matchesTopics(v.vote.topics, topics))
      : [];

  return days.map((day) => {
    const sections = showsKind(filter, 'debate')
      ? day.digests.flatMap((digest) =>
          sectionItems(digest).filter((s) =>
            matchesTopics(sectionTopics(s.section), topics),
          ),
        )
      : [];
    const heat = dayHeat(sections);
    // Stable sort: ties and uncounted debates keep stored order (Bundestag
    // first, protocol order).
    const rate = (item: SectionItem) => interjectionRate(item) ?? -1;
    const ranked = [...sections].sort((a, b) => rate(b) - rate(a));
    // A day with no counted debate has nothing to crown.
    const hot = ranked.find((s) => interjectionRate(s) !== null) ?? null;

    const debated = new Set(hot?.section.drucksachen ?? []);
    const match =
      day.digests
        .flatMap(visibleVotes)
        .find((v) => (v.vote.drucksachen ?? []).some((d) => debated.has(d))) ??
      null;

    const blocks = day.digests
      .map((digest) => ({
        digest,
        sections: ranked.filter(
          (s) => s.digest.id === digest.id && s.key !== hot?.key,
        ),
        votes: visibleVotes(digest).filter((v) => v.key !== match?.key),
      }))
      .filter((b) => b.sections.length > 0 || b.votes.length > 0);

    return { date: day.date, hot, match, blocks, heat };
  });
}
