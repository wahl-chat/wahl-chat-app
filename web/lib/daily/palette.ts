import type { SeatVote } from './hemicycle';

/**
 * Colours of the /aktuell editorial theme. Plain hex (not Tailwind classes)
 * because the hemicycle SVG and inline styles need literal values. Topic fills
 * keep the same colour in both themes, so their text colour is fixed too.
 */

const INK = '#1A1A1A';
const PAPER = '#FFFFFF';

export type TopicSwatch = { fill: string; fg: string };

export const TOPIC_SWATCHES: Record<string, TopicSwatch> = {
  economy_finance: { fill: '#E9C46A', fg: INK },
  social_labor: { fill: '#F2CC8F', fg: INK },
  education_research: { fill: '#F1A7A7', fg: INK },
  climate_environment: { fill: '#81B29A', fg: INK },
  health_care: { fill: '#E07A5F', fg: INK },
  digitalization_tech: { fill: '#A8DADC', fg: INK },
  migration_integration: { fill: '#E76F51', fg: INK },
  security_justice: { fill: '#457B9D', fg: PAPER },
  // The second blue, so the two foreign/security topics stay apart.
  foreign_policy_europe: { fill: '#3D5A80', fg: PAPER },
  transport_infrastructure: { fill: '#9C89B8', fg: INK },
  housing_rent: { fill: '#DDA15E', fg: INK },
  other: { fill: '#D8D2C4', fg: INK },
};

export function topicSwatch(topic: string): TopicSwatch {
  return TOPIC_SWATCHES[topic] ?? TOPIC_SWATCHES.other;
}

/** Grounded variants of the party colours; unlisted parties keep the colour
 * the digest carries. Values may be CSS variables (theme-dependent), so apply
 * them through `style`, never as SVG presentation attributes. */
const PARTY_COLORS: Record<string, string> = {
  linke: '#B23A48',
  spd: '#C8463D',
  gruene: '#4F7942',
  cdu: 'var(--daily-party-cdu)',
  csu: '#3E7CB1',
  afd: '#3F88B5',
  fdp: '#E9C46A',
  bsw: '#7B3F61',
  fw: '#E39B3B',
  ssw: '#1F4E79',
  fraktionslos: '#A39E93',
  fraktionslose: '#A39E93',
  unbekannt: '#A39E93',
};

export function partyColor(partyId: string, fallback: string): string {
  return PARTY_COLORS[partyId] ?? fallback;
}

/** Absent seats are drawn hollow, so they have a stroke but no fill colour. */
export const SEAT_FILLS: Record<Exclude<SeatVote, 'absent'>, string> = {
  yes: '#3F8F5F',
  abstain: '#E9C46A',
  no: '#D1495B',
};

export const STAMP_COLORS = {
  angenommen: 'var(--daily-stamp-yes)',
  abgelehnt: 'var(--daily-stamp-no)',
  close: '#E9C46A',
} as const;
