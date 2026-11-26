import DailyFeed from '@/components/daily/daily-feed';
import JsonLd from '@/components/seo/json-ld';
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
  getStimmtsStatus,
} from '@/lib/firebase/firebase-server';
import type { FeedPage } from '@/lib/firebase/firebase.types';
import {
  BASE_URL,
  LOGO_IMAGE_URL,
  ORGANIZATION_ID,
  WEBSITE_ID,
  productionRobots,
} from '@/lib/seo';
import { hasPuzzleToday } from '@/lib/stimmts/feed-entry';
import type { StimmtsStatus } from '@/lib/stimmts/status';
import { IS_EMBEDDED } from '@/lib/utils';
import type { Metadata } from 'next';
import { headers } from 'next/headers';

// The search terms lead the title, the product name closes it. A results
// page shows about 60 characters of a title and 155 of a description, so
// the brand at the end is what gets cut first.
const TITLE =
  'Dein Bundestag kompakt: Debatten & Abstimmungen – wahl.chat News';
const DESCRIPTION =
  'Verstehe, was im Bundestag passiert: Debatten und Abstimmungen Tag für Tag kompakt zusammengefasst, nach Themen gefiltert und mit Quellen belegt.';

// What the page is about, as entities: a regularly updated collection of the
// Bundestag's debates and votes, published by wahl.chat.
const PAGE_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'CollectionPage',
  '@id': `${BASE_URL}/#webpage`,
  name: TITLE,
  description: DESCRIPTION,
  url: BASE_URL,
  inLanguage: 'de',
  isPartOf: { '@id': WEBSITE_ID },
  publisher: { '@id': ORGANIZATION_ID },
  about: {
    '@type': 'GovernmentOrganization',
    name: 'Deutscher Bundestag',
    url: 'https://www.bundestag.de',
    sameAs: 'https://de.wikipedia.org/wiki/Deutscher_Bundestag',
  },
  keywords:
    'Bundestag, Plenarsitzung, Debatten, Abstimmungen, Plenarprotokoll, Parteipositionen',
};

const FEED_METADATA: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  robots: productionRobots,
  alternates: {
    canonical: '/',
  },
  openGraph: {
    // Absolute, or the root layout's template appends a second brand.
    title: { absolute: TITLE },
    description: DESCRIPTION,
    url: BASE_URL,
    // This openGraph replaces the root layout's whole, image included.
    images: [LOGO_IMAGE_URL],
  },
  twitter: {
    title: TITLE,
    description: DESCRIPTION,
    images: [LOGO_IMAGE_URL],
  },
};

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
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/** A shared item's link previews as the item; the feed itself as the feed. */
export async function generateMetadata({
  searchParams,
}: Props): Promise<Metadata> {
  const { item: key } = await searchParams;
  const item = typeof key === 'string' ? await getLinkedItem(key) : undefined;
  if (!item) {
    return FEED_METADATA;
  }
  return {
    ...FEED_METADATA,
    ...itemShareMetadata(item, await requestOrigin(), DESCRIPTION),
  };
}

const NO_FEED: FeedPage = {
  editions: [],
  items: [],
  from: null,
  hasOlder: false,
};

async function HomePage({ searchParams }: Props) {
  const params = await searchParams;

  // Only the Bundestag is in the feed for now (see `DAILY_STATES`).
  const item = typeof params.item === 'string' ? params.item : undefined;
  const [
    bundestag,
    previewDigests,
    linkedDay,
    calendar,
    editionDates,
    glossary,
    stimmtsStatus,
  ] = await Promise.all([
    getParliamentFeed('bundestag'),
    getLocalPreviewDigests(),
    item ? getLinkedFeedDay(item) : null,
    getSittingCalendar('bundestag'),
    getEditionDates('bundestag'),
    getGlossary(),
    getStimmtsStatus(),
  ]);
  // The page renders per request, so it can tell whether a puzzle runs
  // today. With none (before the launch, after the last puzzle) the server
  // draws no card, rather than one the browser would then remove.
  const stimmtsCardStatus: StimmtsStatus = hasPuzzleToday(
    stimmtsStatus,
    new Date(),
  )
    ? stimmtsStatus
    : { enabled: false };

  return (
    <>
      <JsonLd data={PAGE_JSON_LD} />
      <DailyFeed
        feeds={{
          bundestag,
          landtag_st: NO_FEED,
          landtag_bw: NO_FEED,
        }}
        previewDigests={previewDigests}
        initialStates={parseStateParam(params.land)}
        initialFilter={{
          topics: parseTopicsParam(params.themen),
          kinds: parseKindParam(params.inhalt),
        }}
        initialItem={item}
        linkedDay={linkedDay}
        calendar={calendar}
        editionDates={editionDates}
        glossary={glossary}
        opinionsEnabled={!IS_EMBEDDED}
        stimmtsStatus={stimmtsCardStatus}
      />
    </>
  );
}

export default HomePage;
