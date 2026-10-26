import DailyFeed from '@/components/daily/daily-feed';
import { getLocalPreviewDigests } from '@/lib/daily/local-preview';
import { parseStateParam } from '@/lib/daily/region';
import { parseTopicsParam } from '@/lib/daily/topics';
import { getParliamentFeed } from '@/lib/firebase/firebase-server';
import {
  localeAlternates,
  localizedUrl,
  productionRobots,
  resolveLocale,
} from '@/lib/seo';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const t = await getTranslations({ locale, namespace: 'meta.feed' });
  const title = t('title');
  const description = t('description');

  return {
    title: { absolute: title },
    description,
    robots: productionRobots,
    alternates: localeAlternates('/', locale),
    openGraph: {
      title,
      description,
      url: localizedUrl('/', locale),
    },
    twitter: {
      title,
      description,
    },
  };
}

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

async function HomePage({ searchParams }: Props) {
  const params = await searchParams;

  // All three parliaments are small, so switching the state stays client-side.
  const [bundestag, landtagSt, landtagBw, previewDigests] = await Promise.all([
    getParliamentFeed('bundestag'),
    getParliamentFeed('landtag_st'),
    getParliamentFeed('landtag_bw'),
    getLocalPreviewDigests(),
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
      initialItem={typeof params.item === 'string' ? params.item : undefined}
    />
  );
}

export default HomePage;
