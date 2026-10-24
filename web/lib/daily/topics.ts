import { TOPIC_TITLES } from '@/components/topics/topics.data';
import type { FeedLocale } from '@/lib/firebase/firebase.types';

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

const TITLES_EN: Record<string, string> = {
  economy_finance: 'Economy and finance',
  social_labor: 'Social affairs and labour',
  education_research: 'Education and research',
  climate_environment: 'Climate and environment',
  health_care: 'Health and care',
  digitalization_tech: 'Digital and technology',
  migration_integration: 'Migration and integration',
  security_justice: 'Security and justice',
  foreign_policy_europe: 'Foreign policy and Europe',
  transport_infrastructure: 'Transport and infrastructure',
  housing_rent: 'Housing and rent',
  other: 'Other topics',
};

export function topicTitle(topic: string, locale: FeedLocale = 'de'): string {
  if (locale === 'en') {
    return TITLES_EN[topic] ?? TITLES_EN.other;
  }
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

const SHORT_TITLES_EN: Record<string, string> = {
  economy_finance: 'Economy',
  social_labor: 'Social',
  education_research: 'Education',
  climate_environment: 'Climate',
  health_care: 'Health',
  digitalization_tech: 'Digital',
  migration_integration: 'Migration',
  security_justice: 'Security',
  foreign_policy_europe: 'Foreign policy',
  transport_infrastructure: 'Transport',
  housing_rent: 'Housing',
  other: 'Other',
};

export function topicShortTitle(
  topic: string,
  locale: FeedLocale = 'de',
): string {
  const short = locale === 'en' ? SHORT_TITLES_EN : SHORT_TITLES;
  return short[topic] ?? topicTitle(topic, locale);
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
