import ContactCard from '@/components/home/contact-card';
import GitHubCard from '@/components/home/github-card';
import KnownFrom from '@/components/home/known-from';
import SupportUsCard from '@/components/home/support-us-card';
import HowToIntro from '@/components/how-to-intro';
import DataSources from '@/components/landing/data-sources';
import ElectionLinks from '@/components/landing/election-links';
import ExampleQuestions, {
  type QuestionGroup,
} from '@/components/landing/example-questions';
import LandingChatHero from '@/components/landing/landing-chat-hero';
import LandingFaq from '@/components/landing/landing-faq';
import LandingSection from '@/components/landing/landing-section';
import LandingStats from '@/components/landing/landing-stats';
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
const QUESTIONS_ANCHOR = 'beispielfragen';
// Always rendered, so it is the scroll cue's last resort when neither of the
// election-dependent sections above it has anything to show.
const ABOUT_ANCHOR = 'was-ist-wahl-chat';

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

  // Sample questions for every live election, not just the featured one.
  // Between elections there is nothing upcoming, so fall back to the most
  // recent past one rather than dropping the section entirely.
  //
  // Necessarily serial after getContexts(), which is what decides the set. All
  // of these are cached reads issued in parallel, so it is a handful of data
  // cache hits rather than a fan-out of Firestore round trips.
  const questionElections = upcoming.length > 0 ? upcoming : past.slice(0, 1);
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

  const electionContentById = new Map(
    electionContent.map((content) => [content.context.context_id, content]),
  );
  const questionGroups: QuestionGroup[] = questionElections
    .map((context) => electionContentById.get(context.context_id))
    .filter((group): group is QuestionGroup =>
      Boolean(group?.questions.length),
    );
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
    <>
      <JsonLd data={jsonLd} />

      {featuredElection ? (
        <LandingChatHero
          contexts={contexts}
          initialContextId={featuredElection.context_id}
          partiesByContext={partiesByContext}
          fallbackQuestions={homeQuestions}
          questionsByContext={questionsByContext}
          initialSystemStatus={systemStatus}
          hasValidServerUser={!user?.isAnonymous}
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

      {hasElections && (
        <LandingSection id={ELECTIONS_ANCHOR} title="Wahlen auf wahl.chat">
          <ElectionLinks upcoming={upcoming} past={past} />
        </LandingSection>
      )}

      {/* Press coverage and usage figures are the same claim from two sides —
          how wahl.chat has been received — so they share one heading. Each band
          keeps its own labelled divider under it. KnownFrom's own margins are
          dropped here: the h2 already provides the gap above "Bekannt aus:",
          and the two together left a hole big enough to read as a missing
          heading. */}
      {!IS_EMBEDDED && (
        <LandingSection
          title="Rezeption"
          className="py-8 md:py-10"
          contentClassName="max-w-3xl"
        >
          <div className="flex flex-col gap-10">
            <KnownFrom className="my-0 md:mt-0" trailingSeparator={false} />
            <LandingStats electionCount={contexts.length} />
          </div>
        </LandingSection>
      )}

      {questionGroups.length > 0 && (
        <LandingSection
          id={QUESTIONS_ANCHOR}
          title="Beispielfragen an die Parteien"
        >
          <ExampleQuestions groups={questionGroups} />
        </LandingSection>
      )}

      <LandingSection
        id={ABOUT_ANCHOR}
        title="Was ist wahl.chat?"
        className="bg-muted/30"
      >
        <div className="text-muted-foreground">
          <HowToIntro />
        </div>
      </LandingSection>

      {featuredElection && (
        <LandingSection
          title="Welche Daten werden verwendet?"
          className="bg-muted/30"
        >
          <DataSources
            sourcesHref={`/${featuredElection.context_id}/sources`}
          />
        </LandingSection>
      )}

      <LandingSection title="Häufige Fragen">
        <LandingFaq />
      </LandingSection>

      {!IS_EMBEDDED && (
        <LandingSection title="wahl.chat unterstützen">
          <div className="grid gap-4 md:grid-cols-3">
            <SupportUsCard titleAs="h3" />
            <GitHubCard titleAs="h3" />
            <ContactCard titleAs="h3" />
          </div>
        </LandingSection>
      )}
    </>
  );
}
