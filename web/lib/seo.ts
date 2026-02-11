import type { Context } from '@/lib/firebase/firebase.types';
import type { Metadata } from 'next';

const BASE_URL = 'https://wahl.chat';

const IS_PRODUCTION = process.env.SITE_URL === 'https://wahl.chat';

export const productionRobots = IS_PRODUCTION
  ? 'index, follow'
  : 'noindex, nofollow';

export function buildContextMetadata(
  context: Context,
  pageSuffix?: string,
  noIndex?: boolean,
): Metadata {
  const title = pageSuffix
    ? `${pageSuffix} – ${context.name}`
    : `${context.name} – Parteipositionen im Chat vergleichen`;

  const description =
    context.date !== null && context.date.length > 0
      ? `Vergleiche die Positionen der Parteien zur ${context.name} (${context.location_name}). Stelle Fragen zu politischen Themen und erhalte quellengestützte Antworten.`
      : `Vergleiche die Positionen der Parteien in ${context.location_name}. Stelle Fragen zu politischen Themen und erhalte quellengestützte Antworten.`;

  const url = `${BASE_URL}/${context.context_id}`;

  return {
    title,
    description,
    robots: productionRobots,
    openGraph: {
      title,
      description,
      url,
    },
    twitter: {
      title,
      description,
    },
    ...(noIndex && {
      robots: 'noindex',
    }),
  };
}

export function buildContextJsonLd(context: Context) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: `${context.name} – wahl.chat`,
    description:
      context.date !== null && context.date.length > 0
        ? `Parteipositionen für ${context.name} in ${context.location_name} vergleichen.`
        : `Parteipositionen in ${context.location_name} vergleichen.`,
    url: `${BASE_URL}/${context.context_id}`,
    isPartOf: {
      '@type': 'WebSite',
      name: 'wahl.chat',
      url: BASE_URL,
    },
  };
}
