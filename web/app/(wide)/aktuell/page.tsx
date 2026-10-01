import DailyFeed from '@/components/daily/daily-feed';
import { parseStateParam, stateFromGeo } from '@/lib/daily/region';
import { parseTopicsParam } from '@/lib/daily/topics';
import { getDailyDigests } from '@/lib/firebase/firebase-server';
import type { Metadata } from 'next';
import { headers } from 'next/headers';

export const metadata: Metadata = {
  title: 'Was im Parlament passiert ist',
  description:
    'Abstimmungen und Debatten aus Bundestag und Landtag, Tag für Tag und nach Themen gefiltert.',
  alternates: {
    canonical: '/aktuell',
  },
  // Prototype: kept out of search until the feed is populated in production.
  robots: 'noindex',
};

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

async function AktuellPage({ searchParams }: Props) {
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

export default AktuellPage;
