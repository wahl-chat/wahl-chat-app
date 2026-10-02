import { TOPIC_TITLES } from '@/components/topics/topics.data';
import type { DigestSessionSection } from '@/lib/firebase/firebase.types';

/** The site's topic keys and titles plus `other`, which the digest builder
 * uses for items no topic fits (kept in sync by a backend test). Colours come
 * from the feed's own palette (`palette.ts`), not the site's chip classes. */
export const DAILY_TOPICS: Record<string, { title: string }> = {
  ...Object.fromEntries(
    Object.entries(TOPIC_TITLES).map(([key, { title }]) => [key, { title }]),
  ),
  other: { title: 'Weitere Themen' },
};

export const DAILY_TOPIC_KEYS = Object.keys(DAILY_TOPICS);

export function topicTitle(topic: string): string {
  return DAILY_TOPICS[topic]?.title ?? DAILY_TOPICS.other.title;
}

/** No selection means "everything". */
export function matchesTopics(
  itemTopics: readonly string[],
  selected: readonly string[],
): boolean {
  return selected.length === 0 || itemTopics.some((t) => selected.includes(t));
}

export function splitSections(
  sections: readonly DigestSessionSection[],
  selected: readonly string[],
) {
  const visible: DigestSessionSection[] = [];
  const hidden: DigestSessionSection[] = [];
  for (const section of sections) {
    (matchesTopics([section.topic], selected) ? visible : hidden).push(section);
  }
  return { visible, hidden };
}

function joinGerman(items: string[]): string {
  if (items.length <= 1) {
    return items.join('');
  }
  return `${items.slice(0, -1).join(', ')} und ${items.at(-1)}`;
}

/**
 * The closing line of every session summary. It names whatever the reader is
 * NOT seeing — sections hidden by the topic filter plus the minor agenda items
 * that never got a section — so a narrow filter never reads as "that was all".
 */
export function otherTopicsSentence(
  hiddenSections: readonly DigestSessionSection[],
  otherTopics: readonly string[],
): string {
  const names = [
    ...new Set([
      ...hiddenSections.map((s) => s.headline),
      ...otherTopics.map((t) => t.trim()).filter(Boolean),
    ]),
  ];
  if (names.length === 0) {
    return 'Weitere Themen standen in dieser Sitzung nicht auf der Tagesordnung.';
  }
  return `Außerdem ging es um ${joinGerman(names)}.`;
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
