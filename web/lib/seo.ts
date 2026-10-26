import { DEFAULT_LOCALE, LOCALES, type Locale, isLocale } from '@/i18n/locales';
import type { Context } from '@/lib/firebase/firebase.types';
import { IS_EMBEDDED, formatDate } from '@/lib/utils';
import deMessages from '@/messages/de';
import enMessages from '@/messages/en';
import type { Metadata } from 'next';
import { createTranslator } from 'next-intl';

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

/** The `[locale]` route param, narrowed; anything unknown reads as German. */
export function resolveLocale(value: string | undefined): Locale {
  return isLocale(value) ? value : DEFAULT_LOCALE;
}

/** `/chat` in `en` → `/en/chat`. German keeps its unprefixed URLs. */
export function localizedPath(path: string, locale: Locale): string {
  if (locale === DEFAULT_LOCALE) {
    return path;
  }
  return path === '/' ? `/${locale}` : `/${locale}${path}`;
}

/** Absolute URL of `path` in `locale`; the German home page stays the bare
 * origin, as it has always been advertised. */
export function localizedUrl(path: string, locale: Locale): string {
  const localized = localizedPath(path, locale);
  return localized === '/' ? BASE_URL : `${BASE_URL}${localized}`;
}

/**
 * Canonical plus hreflang for an indexable page that exists in every
 * language. The canonical points at the page's own language, so an English
 * page is not folded into its German twin, and `x-default` sends readers of
 * any other language to German, the site's primary audience.
 */
export function localeAlternates(
  path: string,
  locale: Locale = DEFAULT_LOCALE,
): NonNullable<Metadata['alternates']> {
  return {
    canonical: localizedPath(path, locale),
    languages: {
      ...Object.fromEntries(LOCALES.map((l) => [l, localizedPath(path, l)])),
      'x-default': localizedPath(path, DEFAULT_LOCALE),
    },
  };
}

// Synchronous on purpose: these helpers are spread into metadata objects by
// callers that do not await them, so they read the catalogs directly instead
// of going through the request-scoped getTranslations().
const CATALOGS = { de: deMessages, en: enMessages } as const;

function metaTranslator(locale: Locale) {
  return createTranslator({
    locale,
    messages: CATALOGS[locale],
    namespace: 'meta.context',
  });
}

type ContextMetadataOptions = {
  /** Already translated page name shown before the context name, e.g. 'Quellen'. */
  pageSuffix?: string;
  /** Sub-path under the context, e.g. 'sources'. */
  path?: string;
  locale?: Locale;
};

function buildContextUrlPath(context: Context, path?: string): string {
  return `/${context.context_id}${path ? `/${path}` : ''}`;
}

/**
 * Canonical and hreflang for an indexable context page.
 *
 * Deliberately not part of buildContextMetadata: that helper is called from
 * app/[contextId]/layout.tsx, and Next merges metadata field-by-field down the
 * tree, so a canonical set there would be inherited by the noindex /session,
 * /swiper and /share routes. Emit it from the page instead.
 */
export function buildContextCanonical(
  contextId: string,
  path?: string,
  locale: Locale = DEFAULT_LOCALE,
): Metadata {
  return {
    alternates: localeAlternates(
      `/${contextId}${path ? `/${path}` : ''}`,
      locale,
    ),
  };
}

export function buildContextMetadata(
  context: Context,
  { pageSuffix, path, locale = DEFAULT_LOCALE }: ContextMetadataOptions = {},
): Metadata {
  const t = metaTranslator(locale);
  const title = pageSuffix
    ? t('pageTitle', { page: pageSuffix, name: context.name })
    : t('title', { name: context.name });

  // context.date is a Date at runtime (see getContext in firebase-server.ts),
  // so it must not be treated as a string here.
  const electionDate = formatDate(context.date, locale);

  const description = electionDate
    ? t('descriptionWithDate', { name: context.name, date: electionDate })
    : t('descriptionWithoutDate', { location: context.location_name });

  return {
    title,
    description,
    robots: productionRobots,
    openGraph: {
      title,
      description,
      url: localizedUrl(buildContextUrlPath(context, path), locale),
    },
    twitter: {
      title,
      description,
    },
  };
}

export function buildContextJsonLd(
  context: Context,
  path?: string,
  locale: Locale = DEFAULT_LOCALE,
) {
  const t = metaTranslator(locale);
  const electionDate = formatDate(context.date, locale);
  const url = localizedUrl(buildContextUrlPath(context, path), locale);

  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    '@id': `${url}#webpage`,
    name: `${context.name} – wahl.chat`,
    description: electionDate
      ? t('jsonLdDescriptionWithDate', {
          name: context.name,
          location: context.location_name,
          date: electionDate,
        })
      : t('jsonLdDescriptionWithoutDate', {
          location: context.location_name,
        }),
    url,
    inLanguage: locale,
    isPartOf: { '@id': WEBSITE_ID },
  };
}

/**
 * FAQPage mainEntity nodes.
 *
 * Worth stating plainly: Google restricted FAQ rich results to authoritative
 * government and health sites in August 2023, so this will not produce a rich
 * snippet for wahl.chat. It is kept as entity data — Bing still renders it,
 * and answer engines consume it. The reason the FAQ earns its place on / is
 * that the answers are real crawlable text, not this markup.
 *
 * The text passed in must be the text the page actually shows: structured data
 * describing hidden content is a policy violation, which is also why the FAQ
 * uses <details> rather than an accordion that unmounts closed answers.
 */
export function buildFaqPageMainEntity(
  items: { question: string; answer: string }[],
) {
  return items.map(({ question, answer }) => ({
    '@type': 'Question',
    name: question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: answer,
    },
  }));
}
