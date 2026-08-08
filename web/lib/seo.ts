import type { Context } from '@/lib/firebase/firebase.types';
import { IS_EMBEDDED, formatGermanDate } from '@/lib/utils';
import type { Metadata } from 'next';

export const BASE_URL = 'https://wahl.chat';

// VERCEL_ENV is injected by Vercel and is 'production' only on production
// deployments, so previews and local dev stay noindex without depending on a
// manually configured variable.
//
// The embed deployment (embed.wahl.chat) serves the same routes from the same
// codebase, so without the IS_EMBEDDED check it is a full duplicate of the site
// competing with wahl.chat for every URL.
export const IS_INDEXABLE =
  process.env.VERCEL_ENV === 'production' && !IS_EMBEDDED;

export const productionRobots = IS_INDEXABLE
  ? 'index, follow'
  : 'noindex, nofollow';

// Stable node identifiers so every page references one Organization and one
// WebSite entity instead of re-declaring detached copies of them.
export const ORGANIZATION_ID = `${BASE_URL}/#organization`;
export const WEBSITE_ID = `${BASE_URL}/#website`;

type ContextMetadataOptions = {
  /** Appended before the context name in the title, e.g. 'Quellen'. */
  pageSuffix?: string;
  /** Sub-path under the context, e.g. 'sources'. */
  path?: string;
};

function buildContextUrlPath(context: Context, path?: string): string {
  return `/${context.context_id}${path ? `/${path}` : ''}`;
}

/**
 * Canonical for an indexable context page.
 *
 * Deliberately not part of buildContextMetadata: that helper is called from
 * app/[contextId]/layout.tsx, and Next merges metadata field-by-field down the
 * tree, so a canonical set there would be inherited by the noindex /session,
 * /swiper and /share routes. Emit it from the page instead.
 */
export function buildContextCanonical(
  contextId: string,
  path?: string,
): Metadata {
  return {
    alternates: {
      canonical: `/${contextId}${path ? `/${path}` : ''}`,
    },
  };
}

export function buildContextMetadata(
  context: Context,
  { pageSuffix, path }: ContextMetadataOptions = {},
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

  const urlPath = buildContextUrlPath(context, path);

  return {
    title,
    description,
    robots: productionRobots,
    openGraph: {
      title,
      description,
      url: `${BASE_URL}${urlPath}`,
    },
    twitter: {
      title,
      description,
    },
  };
}

export function buildContextJsonLd(context: Context, path?: string) {
  const electionDate = formatGermanDate(context.date);
  const url = `${BASE_URL}${buildContextUrlPath(context, path)}`;

  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    '@id': `${url}#webpage`,
    name: `${context.name} – wahl.chat`,
    description: electionDate
      ? `Parteipositionen für ${context.name} in ${context.location_name} am ${electionDate} vergleichen.`
      : `Parteipositionen in ${context.location_name} vergleichen.`,
    url,
    isPartOf: { '@id': WEBSITE_ID },
  };
}
