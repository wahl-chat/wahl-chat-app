/** What a feed item is: a debate on an agenda item, or a roll-call vote. */
export type FeedKind = 'debate' | 'vote';

export const FEED_KINDS: readonly FeedKind[] = ['debate', 'vote'];

/** What the reader chose to see. No topics means every topic; at least one
 * kind is always chosen. */
export type FeedFilter = {
  topics: string[];
  kinds: FeedKind[];
};

export const DEFAULT_FILTER: FeedFilter = {
  topics: [],
  kinds: [...FEED_KINDS],
};

export function showsKind(filter: FeedFilter, kind: FeedKind): boolean {
  return filter.kinds.includes(kind);
}

/** How many choices narrow the feed: each topic, plus one when a kind is
 * left out. */
export function activeFilterCount(filter: FeedFilter): number {
  const kindNarrowed = FEED_KINDS.some((kind) => !showsKind(filter, kind));
  return filter.topics.length + (kindNarrowed ? 1 : 0);
}

export function isDefaultFilter(filter: FeedFilter): boolean {
  return activeFilterCount(filter) === 0;
}

export const KIND_PARAM = 'inhalt';

const KIND_PARAM_VALUES: Record<FeedKind, string> = {
  debate: 'debatten',
  vote: 'abstimmungen',
};

/** The URL names a kind only when it is the one shown; both is the default
 * and leaves the param out. */
export function kindParamValue(kinds: readonly FeedKind[]): string | null {
  return kinds.length === 1 ? KIND_PARAM_VALUES[kinds[0]] : null;
}

/** Anything unknown shows both kinds rather than an empty feed. */
export function parseKindParam(
  value: string | string[] | null | undefined,
): FeedKind[] {
  const raw = Array.isArray(value) ? value[0] : value;
  const kind = FEED_KINDS.find((k) => KIND_PARAM_VALUES[k] === raw);
  return kind ? [kind] : [...FEED_KINDS];
}
