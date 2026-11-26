import type { Topic } from '@/components/topics/topics.data';

/** A topic id of the parliament feed (`lib/daily/topics.ts`). */
export type FeedTopic = Topic | 'other';

/**
 * Each puzzle's free-form `topic` word, mapped to the feed topic whose dot
 * colour it shows (`topicColor` in `lib/daily/palette.ts`). The feed has fewer,
 * broader topics, so several words share one. The validator rejects a word
 * missing here, so a new topic word cannot silently lose its dot.
 */
export const FEED_TOPIC_BY_STIMMTS_TOPIC: Record<string, FeedTopic> = {
  // The feed has no energy topic; energy policy sits with climate policy,
  // even where a vote is about prices (Tankrabatt, Stromsteuer).
  Energie: 'climate_environment',
  Umwelt: 'climate_environment',
  Migration: 'migration_integration',
  Asyl: 'migration_integration',
  Verkehr: 'transport_infrastructure',
  Gesundheit: 'health_care',
  Steuern: 'economy_finance',
  Haushalt: 'economy_finance',
  // Consumer contracts are about money people spend, which readers look for
  // under the economy rather than under justice.
  Verbraucherschutz: 'economy_finance',
  Wohnen: 'housing_rent',
  Rente: 'social_labor',
  Soziales: 'social_labor',
  Arbeit: 'social_labor',
  Recht: 'security_justice',
  'Innere Sicherheit': 'security_justice',
  Bildung: 'education_research',
  Außenpolitik: 'foreign_policy_europe',
  // The feed has no defence topic, and its security topic is explicitly the
  // internal one. The Bundeswehr faces outward (Wehrdienst, Ukraine aid,
  // missions abroad), so defence goes with foreign policy.
  Verteidigung: 'foreign_policy_europe',
  // No feed topic covers sport; the feed itself files such items as `other`.
  Sport: 'other',
};

export function feedTopicFor(topic: string): FeedTopic | undefined {
  return Object.hasOwn(FEED_TOPIC_BY_STIMMTS_TOPIC, topic)
    ? FEED_TOPIC_BY_STIMMTS_TOPIC[topic]
    : undefined;
}
