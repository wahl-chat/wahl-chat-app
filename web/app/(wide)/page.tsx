import DailyFeed from '@/components/daily/daily-feed';
import { getLocalPreviewDigests } from '@/lib/daily/local-preview';
import { parseStateParam } from '@/lib/daily/region';
import { parseTopicsParam } from '@/lib/daily/topics';
import {
  getLinkedFeedDay,
  getParliamentFeed,
} from '@/lib/firebase/firebase-server';
import type { FeedPage } from '@/lib/firebase/firebase.types';
import { BASE_URL, productionRobots } from '@/lib/seo';
import type { Metadata } from 'next';

const TITLE = 'Dein Parlament kompakt – wahl.chat';
const DESCRIPTION =
  'Abstimmungen und Debatten aus dem Bundestag, Tag für Tag und nach Themen gefiltert. Mit Quellen, präsentiert von wahl.chat.';

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  robots: productionRobots,
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: TITLE,
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
  const [bundestag, previewDigests, linkedDay] = await Promise.all([
    getParliamentFeed('bundestag'),
    getLocalPreviewDigests(),
    item ? getLinkedFeedDay(item) : null,
  ]);

  return (
    <DailyFeed
      feeds={{
        bundestag,
        landtag_st: NO_FEED,
        landtag_bw: NO_FEED,
      }}
      previewDigests={previewDigests}
      initialStates={parseStateParam(params.land)}
      initialTopics={parseTopicsParam(params.themen)}
      initialItem={item}
      linkedDay={linkedDay}
    />
  );
}

export default HomePage;
