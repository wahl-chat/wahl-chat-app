import type { DigestVoteParty, FeedItem } from '@/lib/firebase/firebase.types';

/** A feed item as the general chat offers it: in the "Aus dem Feed" picker
 * and as an empty-state question. */
export type FeedPick = {
  id: string;
  kind: 'debate' | 'vote';
  /** ISO day, `YYYY-MM-DD`. */
  date: string;
  rank: number;
  headline: string;
  questions: string[];
  /** Interjections per minute; null for votes and unmeasured debates. */
  heat: number | null;
  /** A vote's result per Fraktion, drawn as its hemicycle; empty for debates. */
  parties: DigestVoteParty[];
  outcome: 'angenommen' | 'abgelehnt' | null;
  /** The frame the debate's card video opens on. */
  poster: string | null;
  minutes: number | null;
};

export type StarterQuestion = {
  question: string;
  /** The feed item the question is about; it becomes the chat's anchor. */
  feedItemId?: string;
};

export const WEEK_QUESTION = 'Was ist diese Woche im Bundestag passiert?';

const FALLBACK_QUESTIONS = [
  WEEK_QUESTION,
  'Worüber wird im Bundestag gerade diskutiert?',
  'Wie entsteht ein Gesetz im Bundestag?',
  'Welche Abstimmungen gab es zuletzt im Bundestag?',
];

const FEED_STARTERS = 3;

function heat(item: FeedItem): number | null {
  const minutes = item.debate?.debate_minutes;
  const interjections = item.debate?.interjections;
  return minutes && interjections != null ? interjections / minutes : null;
}

/** Published items, newest day first, agenda order within a day. */
export function feedPicks(items: readonly FeedItem[]): FeedPick[] {
  return items
    .filter((item) => item.status === 'published')
    .map((item) => ({
      id: item.id,
      kind: item.kind,
      date: item.date,
      rank: item.rank,
      headline: item.content.de.headline,
      questions: (item.content.de.suggested_questions ?? []).filter((q) =>
        q.trim(),
      ),
      heat: heat(item),
      parties: item.vote?.parties ?? [],
      outcome: item.vote?.outcome ?? null,
      poster: item.debate?.card_video?.poster_url ?? null,
      minutes: item.debate?.debate_minutes ?? null,
    }))
    .sort((a, b) => b.date.localeCompare(a.date) || a.rank - b.rank);
}

/** Every search term appears in the headline, ignoring case. */
export function filterPicks(
  picks: readonly FeedPick[],
  query: string,
): FeedPick[] {
  const terms = query.toLocaleLowerCase('de').split(/\s+/).filter(Boolean);
  if (terms.length === 0) {
    return [...picks];
  }
  return picks.filter((pick) => {
    const headline = pick.headline.toLocaleLowerCase('de');
    return terms.every((term) => headline.includes(term));
  });
}

/**
 * A new general chat's opening questions. Anchored on a known item: that
 * item's own questions. Otherwise the week question plus one question from
 * each of the newest day's liveliest items, or a fixed list without a feed.
 */
export function starterQuestions(
  picks: readonly FeedPick[],
  anchorFeedItemId?: string,
): StarterQuestion[] {
  const anchored = picks.find((pick) => pick.id === anchorFeedItemId);
  if (anchored && anchored.questions.length > 0) {
    return anchored.questions
      .slice(0, FEED_STARTERS)
      .map((question) => ({ question, feedItemId: anchored.id }));
  }
  const newest = picks.find((pick) => pick.questions.length > 0)?.date;
  const top = picks
    .filter((pick) => pick.date === newest && pick.questions.length > 0)
    .sort((a, b) => (b.heat ?? -1) - (a.heat ?? -1) || a.rank - b.rank)
    .slice(0, FEED_STARTERS);
  if (top.length === 0) {
    return FALLBACK_QUESTIONS.map((question) => ({ question }));
  }
  return [
    { question: WEEK_QUESTION },
    ...top.map((pick) => ({
      question: pick.questions[0],
      feedItemId: pick.id,
    })),
  ];
}

const shortDay = new Intl.DateTimeFormat('de-DE', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
});

/** "Abstimmung · 13. Nov. · angenommen". */
export function pickMeta(pick: FeedPick): string {
  const day = shortDay.format(new Date(`${pick.date}T00:00:00Z`));
  return [pick.kind === 'vote' ? 'Abstimmung' : 'Debatte', day, pick.outcome]
    .filter(Boolean)
    .join(' · ');
}
