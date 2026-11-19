import DailyFeed from '@/components/daily/daily-feed';
import JsonLd from '@/components/seo/json-ld';
import type { Locale } from '@/i18n/locales';
import { parseKindParam } from '@/lib/daily/filter';
import { getLinkedItem } from '@/lib/daily/linked-item';
import { getLocalPreviewDigests } from '@/lib/daily/local-preview';
import { parseStateParam } from '@/lib/daily/region';
import { itemShareMetadata } from '@/lib/daily/share-metadata';
import { parseTopicsParam } from '@/lib/daily/topics';
import {
  getEditionDates,
  getGlossary,
  getLinkedFeedDay,
  getParliamentFeed,
  getSittingCalendar,
} from '@/lib/firebase/firebase-server';
import type { FeedPage } from '@/lib/firebase/firebase.types';
import {
  BASE_URL,
  LOGO_IMAGE_URL,
  ORGANIZATION_ID,
  WEBSITE_ID,
  localeAlternates,
  localizedPath,
  localizedUrl,
  productionRobots,
  resolveLocale,
} from '@/lib/seo';
import { IS_EMBEDDED } from '@/lib/utils';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import { headers } from 'next/headers';

type FeedCopy = { title: string; description: string; keywords: string };

async function feedCopy(locale: Locale): Promise<FeedCopy> {
  // The search terms lead the title, the product name closes it. A results
  // page shows about 60 characters of a title and 155 of a description, so
  // the brand at the end is what gets cut first.
  const t = await getTranslations({ locale, namespace: 'meta.feed' });
  return {
    title: t('title'),
    description: t('description'),
    keywords: t('keywords'),
  };
}

// What the page is about, as entities: a regularly updated collection of the
// Bundestag's debates and votes, published by wahl.chat.
function pageJsonLd(locale: Locale, copy: FeedCopy) {
  return {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    '@id': `${BASE_URL}${localizedPath('/', locale)}#webpage`,
    name: copy.title,
    description: copy.description,
    url: localizedUrl('/', locale),
    inLanguage: locale,
    isPartOf: { '@id': WEBSITE_ID },
    publisher: { '@id': ORGANIZATION_ID },
    about: {
      '@type': 'GovernmentOrganization',
      name: 'Deutscher Bundestag',
      url: 'https://www.bundestag.de',
      sameAs: 'https://de.wikipedia.org/wiki/Deutscher_Bundestag',
    },
    keywords: copy.keywords,
  };
}

function feedMetadata(locale: Locale, copy: FeedCopy): Metadata {
  const { title, description } = copy;
  return {
    title: { absolute: title },
    description,
    robots: productionRobots,
    alternates: localeAlternates('/', locale),
    openGraph: {
      // Absolute, or the root layout's template appends a second brand.
      title: { absolute: title },
      description,
      url: localizedUrl('/', locale),
      // This openGraph replaces the root layout's whole, image included.
      images: [LOGO_IMAGE_URL],
    },
    twitter: {
      title,
      description,
      images: [LOGO_IMAGE_URL],
    },
  };
}

/** The address this request reached, so a link shared from a preview
 * deployment previews with that deployment's own image. */
async function requestOrigin(): Promise<string> {
  const headersList = await headers();
  const host = headersList.get('x-forwarded-host') ?? headersList.get('host');
  if (!host) {
    return BASE_URL;
  }
  const proto =
    headersList.get('x-forwarded-proto') ??
    (host.startsWith('localhost') ? 'http' : 'https');
  return `${proto}://${host}`;
}

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/** A shared item's link previews as the item; the feed itself as the feed. */
export async function generateMetadata({
  params,
  searchParams,
}: Props): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const copy = await feedCopy(locale);
  const metadata = feedMetadata(locale, copy);
  const { item: key } = await searchParams;
  const item =
    typeof key === 'string' ? await getLinkedItem(key, locale) : undefined;
  if (!item) {
    return metadata;
  }
  return {
    ...metadata,
    ...itemShareMetadata(item, await requestOrigin(), copy.description, locale),
  };
}

const NO_FEED: FeedPage = {
  editions: [],
  items: [],
  from: null,
  hasOlder: false,
};

async function HomePage({ params, searchParams }: Props) {
  const locale = resolveLocale((await params).locale);
  const query = await searchParams;

  // Only the Bundestag is in the feed for now (see `DAILY_STATES`).
  const item = typeof query.item === 'string' ? query.item : undefined;
  const [
    copy,
    bundestag,
    previewDigests,
    linkedDay,
    calendar,
    editionDates,
    glossary,
  ] = await Promise.all([
    feedCopy(locale),
    getParliamentFeed('bundestag'),
    getLocalPreviewDigests(),
    item ? getLinkedFeedDay(item) : null,
    getSittingCalendar('bundestag'),
    getEditionDates('bundestag'),
    getGlossary(),
  ]);

  return (
    <>
      <JsonLd data={pageJsonLd(locale, copy)} />
      <DailyFeed
        feeds={{
          bundestag,
          landtag_st: NO_FEED,
          landtag_bw: NO_FEED,
        }}
        previewDigests={previewDigests}
        initialStates={parseStateParam(query.land)}
        initialFilter={{
          topics: parseTopicsParam(query.themen),
          kinds: parseKindParam(query.inhalt),
        }}
        initialItem={item}
        linkedDay={linkedDay}
        calendar={calendar}
        editionDates={editionDates}
        glossary={glossary}
        opinionsEnabled={!IS_EMBEDDED}
      />
    </>
  );
}

export default HomePage;
