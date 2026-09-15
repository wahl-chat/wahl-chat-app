import KnownFrom from '@/components/home/known-from';
import ElectionLinks from '@/components/landing/election-links';
import LandingChatHero from '@/components/landing/landing-chat-hero';
import LandingCommunity from '@/components/landing/landing-community';
import { LandingComposerProvider } from '@/components/landing/landing-composer-provider';
import LandingExplainer from '@/components/landing/landing-explainer';
import LandingSection from '@/components/landing/landing-section';
import JsonLd from '@/components/seo/json-ld';
import { splitElectionsByDate } from '@/lib/elections';
import {
  getContexts,
  getGroupProposedQuestionsForContext,
  getHomeInputProposedQuestions,
  getPartiesForContext,
  getSystemStatus,
  getUser,
} from '@/lib/firebase/firebase-server';
import {
  flattenAccordionContentToText,
  getLandingFaqItems,
} from '@/lib/how-to-content';
import {
  BASE_URL,
  WEBSITE_ID,
  buildFaqPageMainEntity,
  productionRobots,
} from '@/lib/seo';
import { IS_EMBEDDED, shuffleArray } from '@/lib/utils';
import type { Metadata } from 'next';

// The featured election is derived from the context dates, so it rolls over on
// its own once the current one concludes, and the output does not depend on the
// requester — crawlers and visitors get the same page, which the geo redirect
// this replaced could not promise. Freshness comes from the context read, which
// is cached and busted by tag on seed.
//
// This export is documentation rather than mechanism: the root layout awaits
// headers(), which already opts every route out of static generation.
export const dynamic = 'force-dynamic';

// Under 60 characters so the SERP title is not truncated; the description
// stays inside 140–155 for the same reason and ends on a CTA.
const TITLE = 'Mit wahl.chat Politik verstehen – dein KI Chat vor der Wahl';
const DESCRIPTION =
  'Die KI-basierte Ergänzung zum Wahl-O-Mat: Verstehe Parteien anhand von Plenarprotokollen, Abstimmungen und Wahlprogrammen. Jetzt informiert wählen!';

const ELECTIONS_ANCHOR = 'andere-wahlen';

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
  const contexts = await getContexts();
  const { upcoming, past } = splitElectionsByDate(contexts);

  // Between elections there is nothing upcoming; fall back to the most recent
  // one so the page still leads somewhere rather than dead-ending.
  const featuredElection = upcoming[0] ?? past[0];

  const [homeQuestions, systemStatus, user, electionContent] =
    await Promise.all([
      getHomeInputProposedQuestions(),
      getSystemStatus(),
      getUser(),
      Promise.all(
        contexts.map(async (context) => {
          const [questions, parties] = await Promise.all([
            getGroupProposedQuestionsForContext(context.context_id),
            getPartiesForContext(context.context_id),
          ]);

          return { context, questions, parties };
        }),
      ),
    ]);

  const partiesByContext = Object.fromEntries(
    electionContent.map(({ context, parties }) => [
      context.context_id,
      shuffleArray(parties),
    ]),
  );
  const questionsByContext = Object.fromEntries(
    electionContent.map(({ context, questions }) => [
      context.context_id,
      questions,
    ]),
  );

  // The selector is interactive rather than a set of links. Keep every
  // election in this server-rendered list so the crawlable markup and the
  // structured ItemList continue to describe the same destinations.
  const hasElections = upcoming.length > 0 || past.length > 0;

  const faqItems = getLandingFaqItems();

  // One node for one URL: FAQPage is a WebPage subtype, so a second node
  // claiming BASE_URL would read as a duplicate page entity.
  const webPage = {
    '@type': ['WebPage', 'FAQPage'],
    '@id': `${BASE_URL}/#webpage`,
    name: TITLE,
    description: DESCRIPTION,
    url: BASE_URL,
    inLanguage: 'de',
    isPartOf: { '@id': WEBSITE_ID },
    mainEntity: buildFaqPageMainEntity(
      faqItems.map((item) => ({
        question: item.title,
        answer: flattenAccordionContentToText(item.content),
      })),
    ),
  };

  // Every election the page links to, so the structured data and crawlable
  // markup cannot drift apart. Each item points at the @id the context page
  // declares for itself, so the graph resolves rather than repeating a bare URL.
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
      item: { '@id': `${BASE_URL}/${context.context_id}#webpage` },
    })),
  };

  const jsonLd = {
    '@context': 'https://schema.org',
    '@graph': orderedElections.length > 0 ? [webPage, electionList] : [webPage],
  };

  return (
    <LandingComposerProvider
      initialContextId={featuredElection?.context_id ?? ''}
    >
      <JsonLd data={jsonLd} />

      {featuredElection ? (
        <LandingChatHero
          contexts={contexts}
          partiesByContext={partiesByContext}
          fallbackQuestions={homeQuestions}
          questionsByContext={questionsByContext}
          initialSystemStatus={systemStatus}
          hasValidServerUser={Boolean(user && !user.isAnonymous)}
        />
      ) : (
        <section className="px-5 py-16 text-center">
          <h1 className="text-3xl font-bold">
            Politik verstehen mit wahl.chat
          </h1>
          <p className="mt-3 text-muted-foreground">
            Aktuell ist keine Wahl verfügbar.
          </p>
        </section>
      )}

      <LandingExplainer
        sourcesHref={
          featuredElection
            ? `/${featuredElection.context_id}/sources`
            : undefined
        }
      />

      {hasElections && (
        <LandingSection
          id={ELECTIONS_ANCHOR}
          eyebrow="Deine Wahl, deine Themen"
          title="Was bewegt dich vor der Wahl?"
          description="Entdecke die Parteien und Themen deiner Wahl. Eine Frageidee hilft dir beim Einstieg – oder du stellst deine eigene Frage."
        >
          <ElectionLinks
            upcoming={upcoming}
            past={past}
            questionsByContext={questionsByContext}
          />
        </LandingSection>
      )}
      {!IS_EMBEDDED && (
        <>
          <LandingCommunity electionCount={contexts.length} />
          <div className="px-6 pb-12 pt-5 md:pb-14 md:pt-8">
            <KnownFrom
              compact
              className="my-0 md:mt-0"
              trailingSeparator={false}
            />
          </div>
        </>
      )}
    </LandingComposerProvider>
  );
}
