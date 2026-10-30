import DailyFeed from '@/components/daily/daily-feed';
import { getLocalPreviewDigests } from '@/lib/daily/local-preview';
import { parseStateParam } from '@/lib/daily/region';
import { parseTopicsParam } from '@/lib/daily/topics';
import {
  getLinkedFeedDay,
  getParliamentFeed,
} from '@/lib/firebase/firebase-server';
import { BASE_URL, productionRobots } from '@/lib/seo';
import type { Metadata } from 'next';

const TITLE = 'Dein Parlament kompakt – wahl.chat';
const DESCRIPTION =
  'Abstimmungen und Debatten aus Bundestag und Landtag, Tag für Tag und nach Themen gefiltert. Mit Quellen, präsentiert von wahl.chat.';

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

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

async function HomePage({ searchParams }: Props) {
  const params = await searchParams;

  // All three parliaments are small, so switching the state stays client-side.
  const item = typeof params.item === 'string' ? params.item : undefined;
  const [bundestag, landtagSt, landtagBw, previewDigests, linkedDay] =
    await Promise.all([
      getParliamentFeed('bundestag'),
      getParliamentFeed('landtag_st'),
      getParliamentFeed('landtag_bw'),
      getLocalPreviewDigests(),
      item ? getLinkedFeedDay(item) : null,
    ]);

  return (
    <DailyFeed
      feeds={{
        bundestag,
        landtag_st: landtagSt,
        landtag_bw: landtagBw,
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
