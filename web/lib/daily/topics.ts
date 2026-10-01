import { TOPIC_TITLES } from '@/components/topics/topics.data';
import type { DigestSessionSection } from '@/lib/firebase/firebase.types';

type TopicStyle = (typeof TOPIC_TITLES)[keyof typeof TOPIC_TITLES];

/** The site's topic chips plus `other`, which the digest builder uses for
 * items no topic fits (kept in sync by a backend test). */
export const DAILY_TOPICS: Record<string, TopicStyle> = {
  ...TOPIC_TITLES,
  other: {
    title: 'Weitere Themen',
    normal: 'bg-zinc-500/20 text-zinc-500 border-zinc-500/30',
    hover: 'hover:bg-zinc-500/40 hover:text-zinc-600 hover:border-zinc-500/40',
    active:
      'bg-zinc-500 text-white border-zinc-700 hover:bg-zinc-500/80 hover:text-white hover:border-zinc-700',
  },
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
