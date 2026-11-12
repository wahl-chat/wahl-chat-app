import DailyFeed from '@/components/daily/daily-feed';
import JsonLd from '@/components/seo/json-ld';
import { parseKindParam } from '@/lib/daily/filter';
import { getLocalPreviewDigests } from '@/lib/daily/local-preview';
import { parseStateParam } from '@/lib/daily/region';
import { parseTopicsParam } from '@/lib/daily/topics';
import {
  getEditionDates,
  getLinkedFeedDay,
  getParliamentFeed,
  getSittingCalendar,
} from '@/lib/firebase/firebase-server';
import type { FeedPage } from '@/lib/firebase/firebase.types';
import {
  BASE_URL,
  ORGANIZATION_ID,
  WEBSITE_ID,
  productionRobots,
} from '@/lib/seo';
import type { Metadata } from 'next';

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

export const metadata: Metadata = {
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
  },
  twitter: {
    title: TITLE,
    description: DESCRIPTION,
  },
};

const NO_FEED: FeedPage = {
  editions: [],
  items: [],
  from: null,
  hasOlder: false,
};

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

async function HomePage({ searchParams }: Props) {
  const params = await searchParams;

  // Only the Bundestag is in the feed for now (see `DAILY_STATES`).
  const item = typeof params.item === 'string' ? params.item : undefined;
  const [bundestag, previewDigests, linkedDay, calendar, editionDates] =
    await Promise.all([
      getParliamentFeed('bundestag'),
      getLocalPreviewDigests(),
      item ? getLinkedFeedDay(item) : null,
      getSittingCalendar('bundestag'),
      getEditionDates('bundestag'),
    ]);

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
      />
    </>
  );
}

export default HomePage;
