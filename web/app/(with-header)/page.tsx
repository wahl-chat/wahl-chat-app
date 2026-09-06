import { ContextIcon } from '@/components/context-icon';
import BrandBlurBackdrop from '@/components/home/brand-blur-backdrop';
import ContactCard from '@/components/home/contact-card';
import ElectionSwitchLink from '@/components/home/election-switch-link';
import GitHubCard from '@/components/home/github-card';
import HomeInput from '@/components/home/home-input';
import HowToCard from '@/components/home/how-to-card';
import KnownFrom from '@/components/home/known-from';
import LandingIntro from '@/components/home/landing-intro';
import OpenCallCard, {
  getAvailableOpenCallUrl,
} from '@/components/home/open-call-card';
import SupportUsCard from '@/components/home/support-us-card';
import AiDisclaimer from '@/components/legal/ai-disclaimer';
import JsonLd from '@/components/seo/json-ld';
import { Button } from '@/components/ui/button';
import { isUpcomingElection, splitElectionsByDate } from '@/lib/elections';
import {
  getContexts,
  getHomeInputProposedQuestions,
  getSystemStatus,
  getUser,
} from '@/lib/firebase/firebase-server';
import { BASE_URL, WEBSITE_ID, productionRobots } from '@/lib/seo';
import { IS_EMBEDDED, formatGermanDate } from '@/lib/utils';
import { ArrowRightIcon, CalendarIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

// The featured election is derived from election dates, so it rolls over on its
// own once the current one concludes, and the output does not depend on the
// requester — crawlers and visitors get the same page, which the geo redirect
// this replaced could not promise. Freshness comes from the context read, which
// is cached and busted by tag on seed; a page-level revalidate would pin an
// empty list into a shell instead.
export const dynamic = 'force-dynamic';

const TITLE = 'wahl.chat – Parteipositionen zur Wahl im Chat vergleichen';
const DESCRIPTION =
  'Stelle den Parteien deine eigenen Fragen und vergleiche ihre Positionen zu Bundestags-, Landtags- und Kommunalwahlen – mit Quellen aus den Parteidokumenten.';

export const metadata: Metadata = {
  title: {
    absolute: TITLE,
  },
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

export default async function Landing() {
  const [contexts, wahlChatQuestions, systemStatus, user, openCallUrl] =
    await Promise.all([
      getContexts(),
      getHomeInputProposedQuestions(),
      getSystemStatus(),
      getUser(),
      getAvailableOpenCallUrl(),
    ]);

  const { upcoming, past } = splitElectionsByDate(contexts);

  // Between elections there is nothing upcoming; fall back to the most recent
  // one so the page still leads somewhere rather than dead-ending.
  const featuredElection = upcoming[0] ?? past[0];
  const featuredDate = formatGermanDate(featuredElection?.date);

  const webPage = {
    '@type': 'WebPage',
    '@id': `${BASE_URL}/#webpage`,
    name: TITLE,
    description: DESCRIPTION,
    url: BASE_URL,
    isPartOf: { '@id': WEBSITE_ID },
  };

  // / is the site's hub for every election, so it says so in structured data
  // rather than leaving the relationship to be inferred from the link list.
  const orderedElections = [...upcoming, ...past];
  const electionList = {
    '@type': 'ItemList',
    '@id': `${BASE_URL}/#elections`,
    name: 'Wahlen auf wahl.chat',
    numberOfItems: orderedElections.length,
    itemListElement: orderedElections.map((context, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: context.name,
      url: `${BASE_URL}/${context.context_id}`,
    })),
  };

  const jsonLd = {
    '@context': 'https://schema.org',
    '@graph': orderedElections.length > 0 ? [webPage, electionList] : [webPage],
  };

  return (
    <>
      <JsonLd data={jsonLd} />

      {/* Breaks out of main's max-w-xl column: 36rem + 2×6rem is exactly
          max-w-3xl, and below md the -mx-4 cancels main's own padding so the
          colour field reaches the screen edges. */}
      <section className="relative -mx-4 mt-4 overflow-hidden md:-mx-24 md:rounded-lg">
        <BrandBlurBackdrop />

        <div className="relative mx-auto flex max-w-2xl flex-col items-center gap-4 px-4 py-12 text-center md:py-16">
          <h1 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl lg:text-5xl">
            Parteipositionen zur Wahl vergleichen – im Chat, mit Quellen
          </h1>

          <p className="text-base text-muted-foreground md:text-lg">
            Stelle den Parteien deine eigenen Fragen – zu Mieten, Bildung, Klima
            oder Migration. Jede Antwort ist mit Quellen aus den
            Parteidokumenten belegt.
          </p>

          {featuredElection && (
            <div className="mt-2 flex w-full flex-col items-center gap-2">
              <Button
                asChild
                size="lg"
                className="h-auto w-full max-w-md whitespace-normal px-6 py-4 text-base"
              >
                <Link href={`/${featuredElection.context_id}`}>
                  <ContextIcon
                    context={featuredElection}
                    className="size-6 shrink-0"
                  />
                  <span>Zur {featuredElection.name}</span>
                  <ArrowRightIcon aria-hidden="true" />
                </Link>
              </Button>

              {featuredDate && (
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <CalendarIcon
                    className="size-4 shrink-0"
                    aria-hidden="true"
                  />
                  {isUpcomingElection(featuredElection)
                    ? 'Wahl am'
                    : 'Wahl vom'}{' '}
                  {featuredDate}
                </p>
              )}

              <ElectionSwitchLink
                contexts={contexts}
                selectedId={featuredElection.context_id}
              />
            </div>
          )}
        </div>
      </section>

      {featuredElection && (
        <>
          <HomeInput
            className="hidden md:block"
            questions={wahlChatQuestions}
            initialSystemStatus={systemStatus}
            hasValidServerUser={!user?.isAnonymous}
            contextId={featuredElection.context_id}
          />
          <AiDisclaimer className="hidden md:block" />
        </>
      )}

      {!IS_EMBEDDED && <KnownFrom />}

      <section className="grid w-full grid-cols-1 flex-wrap gap-2 md:grid-cols-2 md:gap-2">
        <SupportUsCard />
        <ContactCard />
        <GitHubCard fullWidth={!openCallUrl} />
        {openCallUrl && <OpenCallCard url={openCallUrl} />}
        <HowToCard />
      </section>

      {featuredElection && (
        <>
          <HomeInput
            className="md:hidden"
            questions={wahlChatQuestions}
            initialSystemStatus={systemStatus}
            hasValidServerUser={!user?.isAnonymous}
            contextId={featuredElection.context_id}
          />
          <AiDisclaimer className="md:hidden" />
        </>
      )}

      <LandingIntro upcoming={upcoming} past={past} />
    </>
  );
}
