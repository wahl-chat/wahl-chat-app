import type { SeatVote } from './hemicycle';

/**
 * Colours of the feed. Plain hex (not Tailwind classes) because the
 * hemicycle SVG and inline styles need literal values.
 */

/** Topic dots. Never carry text, so they only need to stay apart. */
export const TOPIC_COLORS: Record<string, string> = {
  economy_finance: '#D9A93A',
  social_labor: '#C98A5B',
  education_research: '#D0789A',
  climate_environment: '#5E9B6F',
  health_care: '#C8604A',
  digitalization_tech: '#4A9BA0',
  migration_integration: '#B5694A',
  security_justice: '#4F6D8F',
  foreign_policy_europe: '#3D5A80',
  transport_infrastructure: '#9C8BC4',
  housing_rent: '#A8825A',
  other: '#A1A1AA',
};

export function topicColor(topic: string): string {
  return TOPIC_COLORS[topic] ?? TOPIC_COLORS.other;
}

/** Absent seats are drawn hollow, so they have a stroke but no fill colour. */
export const SEAT_FILLS: Record<Exclude<SeatVote, 'absent'>, string> = {
  yes: '#2F8A5B',
  abstain: '#D9A93A',
  no: '#C2414B',
};
