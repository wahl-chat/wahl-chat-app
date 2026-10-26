import { TOPIC_TITLES } from '@/components/topics/topics.data';
import type { Messages } from 'next-intl';

/** The site's topic keys plus `other`, which the digest builder uses for
 * items no topic fits (kept in sync by a backend test). Labels live in the
 * `topics` message namespace; colours in the feed's own palette (`palette.ts`). */
export const DAILY_TOPIC_KEYS = [
  ...Object.keys(TOPIC_TITLES),
  'other',
] as const;

export type TopicKey = keyof Messages['topics'];

/** A topic's message key; anything the catalog does not know reads as `other`. */
export function topicKey(topic: string): TopicKey {
  return (DAILY_TOPIC_KEYS as readonly string[]).includes(topic)
    ? (topic as TopicKey)
    : 'other';
}

/** No selection means "everything". */
export function matchesTopics(
  itemTopics: readonly string[],
  selected: readonly string[],
): boolean {
  return selected.length === 0 || itemTopics.some((t) => selected.includes(t));
}

export const TOPICS_PARAM = 'themen';

export function parseTopicsParam(
  value: string | string[] | null | undefined,
): string[] {
  const raw = Array.isArray(value) ? value.join(',') : (value ?? '');
  return [
    ...new Set(raw.split(',').filter((t) => DAILY_TOPIC_KEYS.includes(t))),
  ];
}
