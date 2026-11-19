import TopicsFilterableList from '@/components/topics/topics-filterable-list';
import { Button } from '@/components/ui/button';
import { DEFAULT_LOCALE, isLocale } from '@/i18n/locales';
import { Link } from '@/i18n/navigation';
import {
  getExampleQuestionsShareableChatSession,
  getParties,
} from '@/lib/firebase/firebase-server';
import { buildPartyImageUrl } from '@/lib/utils';
import { ArrowLeftIcon } from 'lucide-react';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import Image from 'next/image';

type Props = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale: requested } = await params;
  const locale = isLocale(requested) ? requested : DEFAULT_LOCALE;
  const t = await getTranslations({ locale, namespace: 'topicsPage' });

  return {
    title: t('meta.title'),
    description: t('meta.description'),
    // Context-less and built around federal parties, so it is not tied to a
    // current election and should not surface for election queries.
    robots: 'noindex',
  };
}

async function TopicsPage() {
  const t = await getTranslations('topicsPage');
  const exampleQuestionsShareableChatSessions =
    await getExampleQuestionsShareableChatSession();
  const allParties = await getParties();
  const partiesToUse = ['spd', 'cdu', 'gruene', 'afd'];
  const parties = allParties.filter((party) =>
    partiesToUse.includes(party.party_id),
  );

  return (
    <>
      <Button variant="link" asChild className="mt-4 px-0">
        <Link href="/">
          <ArrowLeftIcon className="size-4" />
          {t('backToHome')}
        </Link>
      </Button>

      <div className="mt-4 flex flex-row gap-2">
        {parties.map((party) => (
          <div
            key={party.party_id}
            className="flex aspect-square items-center justify-center overflow-hidden rounded-full p-2"
            style={{
              backgroundColor: party.background_color,
            }}
          >
            <Image
              src={buildPartyImageUrl(party.party_id)}
              alt={party.name}
              width={40}
              height={40}
              className="object-contain"
            />
          </div>
        ))}
      </div>

      <h1 className="mt-4 text-2xl font-bold">{t('heading')}</h1>
      <p className="text-sm text-muted-foreground">{t('description')}</p>

      <TopicsFilterableList
        exampleQuestionsShareableChatSessions={
          exampleQuestionsShareableChatSessions
        }
      />
    </>
  );
}

export default TopicsPage;
