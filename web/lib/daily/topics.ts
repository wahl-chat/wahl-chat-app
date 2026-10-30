import { TOPIC_TITLES } from '@/components/topics/topics.data';

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

/** One-word labels for the filter pills and compact meta lines. */
const SHORT_TITLES: Record<string, string> = {
  economy_finance: 'Wirtschaft',
  social_labor: 'Soziales',
  education_research: 'Bildung',
  climate_environment: 'Klima',
  health_care: 'Gesundheit',
  digitalization_tech: 'Digitales',
  migration_integration: 'Migration',
  security_justice: 'Sicherheit',
  foreign_policy_europe: 'Außenpolitik',
  transport_infrastructure: 'Verkehr',
  housing_rent: 'Wohnen',
  other: 'Weitere',
};

export function topicShortTitle(topic: string): string {
  return SHORT_TITLES[topic] ?? topicTitle(topic);
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
