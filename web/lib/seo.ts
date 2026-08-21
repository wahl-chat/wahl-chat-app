import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
import type { Metadata } from 'next';

const BASE_URL = 'https://wahl.chat';

// VERCEL_ENV is injected by Vercel and is 'production' only on production
// deployments, so previews and local dev stay noindex without depending on a
// manually configured variable.
const IS_PRODUCTION = process.env.VERCEL_ENV === 'production';

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

  // context.date is a Date at runtime (see getContext in firebase-server.ts),
  // so it must not be treated as a string here.
  const electionDate = formatGermanDate(context.date);

  const description = electionDate
    ? `Vergleiche die Positionen der Parteien zur ${context.name} am ${electionDate}. Stelle Fragen und erhalte quellengestützte Antworten.`
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
  const electionDate = formatGermanDate(context.date);

  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: `${context.name} – wahl.chat`,
    description: electionDate
      ? `Parteipositionen für ${context.name} in ${context.location_name} am ${electionDate} vergleichen.`
      : `Parteipositionen in ${context.location_name} vergleichen.`,
    url: `${BASE_URL}/${context.context_id}`,
    isPartOf: {
      '@type': 'WebSite',
      name: 'wahl.chat',
      url: BASE_URL,
    },
  };
}
