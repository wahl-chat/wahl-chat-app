import ContactCard from '@/components/home/contact-card';
import ElectionBlurCard from '@/components/home/election-blur-card';
import ElectionSelect from '@/components/home/election-select';
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
import { splitElectionsByDate } from '@/lib/elections';
import {
  getContexts,
  getHomeInputProposedQuestions,
  getSystemStatus,
  getUser,
} from '@/lib/firebase/firebase-server';
import { BASE_URL, WEBSITE_ID, productionRobots } from '@/lib/seo';
import { IS_EMBEDDED } from '@/lib/utils';
import type { Metadata } from 'next';

// The featured election is derived from election dates, so it rolls over on its
// own once the current one concludes. The root layout reads headers(), so this
// renders per request like every other route; getContexts() is cached for an
// hour, and the output does not depend on the requester — crawlers and visitors
// get the same page, which the geo redirect this replaced could not promise.
export const revalidate = 3600;

const TITLE = 'wahl.chat – Parteipositionen zur Wahl im Chat vergleichen';
const DESCRIPTION =
  'Stelle den Parteien deine eigenen Fragen und vergleiche ihre Positionen zu Bundestags-, Landtags- und Kommunalwahlen – mit Quellen aus den Wahlprogrammen.';

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

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    '@id': `${BASE_URL}/#webpage`,
    name: TITLE,
    description: DESCRIPTION,
    url: BASE_URL,
    isPartOf: { '@id': WEBSITE_ID },
  };

  return (
    <>
      <JsonLd data={jsonLd} />

      <div className="mt-4 flex w-full flex-col gap-6">
        <section aria-label="Wahl auswählen">
          <ElectionSelect
            contexts={contexts}
            currentContext={featuredElection}
            label="Deine nächste Wahl:"
            highlight
          />
        </section>

        <section className="flex flex-col gap-3">
          <h1 className="flex items-center justify-center gap-2 text-center text-base font-semibold text-foreground">
            Parteipositionen zur Bundestags-, Landtags- und Kommunalwahl im Chat
            vergleichen
          </h1>

          <ElectionBlurCard className="mt-1" />
        </section>
      </div>

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
