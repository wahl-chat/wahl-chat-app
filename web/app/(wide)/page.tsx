import DailyFeed from '@/components/daily/daily-feed';
import { parseStateParam, stateFromGeo } from '@/lib/daily/region';
import { parseTopicsParam } from '@/lib/daily/topics';
import { getDailyDigests } from '@/lib/firebase/firebase-server';
import { BASE_URL, productionRobots } from '@/lib/seo';
import type { Metadata } from 'next';
import { headers } from 'next/headers';

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
  const headersList = await headers();
  const initialState =
    parseStateParam(params.land) ??
    stateFromGeo(
      headersList.get('x-vercel-ip-country'),
      headersList.get('x-vercel-ip-country-region'),
    );

  // All three parliaments are small, so switching the state stays client-side.
  const [bundestag, landtagSt, landtagBw] = await Promise.all([
    getDailyDigests('bundestag'),
    getDailyDigests('landtag_st'),
    getDailyDigests('landtag_bw'),
  ]);

  return (
    <DailyFeed
      digests={{
        bundestag,
        landtag_st: landtagSt,
        landtag_bw: landtagBw,
      }}
      initialState={initialState}
      initialTopics={parseTopicsParam(params.themen)}
    />
  );
}

export default HomePage;
