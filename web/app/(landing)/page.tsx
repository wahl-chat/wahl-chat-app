import ContactCard from '@/components/home/contact-card';
import GitHubCard from '@/components/home/github-card';
import KnownFrom from '@/components/home/known-from';
import SupportUsCard from '@/components/home/support-us-card';
import HowToIntro from '@/components/how-to-intro';
import BrandBlurBackdrop from '@/components/landing/brand-blur-backdrop';
import DataSources from '@/components/landing/data-sources';
import ElectionLinks from '@/components/landing/election-links';
import ExampleQuestions, {
  type QuestionGroup,
} from '@/components/landing/example-questions';
import HeroCta from '@/components/landing/hero-cta';
import HeroLogo from '@/components/landing/hero-logo';
import LandingFaq from '@/components/landing/landing-faq';
import LandingSection from '@/components/landing/landing-section';
import LandingStats from '@/components/landing/landing-stats';
import ScreenshotWheel from '@/components/landing/screenshot-wheel';
import ScrollCue from '@/components/landing/scroll-cue';
import JsonLd from '@/components/seo/json-ld';
import { isUpcomingElection, splitElectionsByDate } from '@/lib/elections';
import {
  getContexts,
  getGroupProposedQuestionsForContext,
  getPartiesForContext,
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
import { IS_EMBEDDED, formatGermanDate } from '@/lib/utils';
import { CalendarIcon } from 'lucide-react';
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
  const featuredDate = formatGermanDate(featuredElection?.date);

  // Sample questions for every live election, not just the featured one.
  // Between elections there is nothing upcoming, so fall back to the most
  // recent past one rather than dropping the section entirely.
  //
  // Necessarily serial after getContexts(), which is what decides the set. All
  // of these are cached reads issued in parallel, so it is a handful of data
  // cache hits rather than a fan-out of Firestore round trips.
  const questionElections = upcoming.length > 0 ? upcoming : past.slice(0, 1);
  const questionGroups: QuestionGroup[] = (
    await Promise.all(
      questionElections.map(async (context) => {
        const [questions, parties] = await Promise.all([
          getGroupProposedQuestionsForContext(context.context_id),
          getPartiesForContext(context.context_id),
        ]);

        return { context, questions, parties };
      }),
    )
  ).filter((group) => group.questions.length > 0);

  // The elections section lists the ones the hero does not already lead with.
  const otherUpcoming = upcoming.filter(
    (context) => context.context_id !== featuredElection?.context_id,
  );
  const otherPast = past.filter(
    (context) => context.context_id !== featuredElection?.context_id,
  );
  const hasOtherElections = otherUpcoming.length > 0 || otherPast.length > 0;

  // The cue points at whatever section actually comes first, so it never lands
  // on an anchor that an empty election list has removed.
  const firstSectionAnchor = hasOtherElections
    ? ELECTIONS_ANCHOR
    : questionGroups.length > 0
      ? QUESTIONS_ANCHOR
      : ABOUT_ANCHOR;

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

  // Every election the page links to — the hero's featured one plus the
  // section listing the rest — so the structured data and the crawlable markup
  // cannot drift apart. Each item points at the @id the context page declares
  // for itself, so the graph resolves rather than repeating a bare URL.
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

      {/* The hero fills the viewport but is no longer the whole page. svh
          rather than dvh: dvh tracks the mobile URL bar collapsing mid-scroll,
          which would resize the hero and shift every section below it.

          This section is also the clip boundary for BrandBlurBackdrop — the
          blobs are positioned in % of their container and drift past its edge,
          so overflow-hidden here is what keeps them off the rest of the
          document. Every other section is a sibling of this one, never a
          child. */}
      <section className="relative flex min-h-svh w-full flex-col overflow-hidden">
        <BrandBlurBackdrop />
        <ScreenshotWheel />

        {/* Mobile-first three-part hero: the mark sits top-left where a site
            logo belongs, the headline takes the middle, and the call to action
            is pinned to the bottom of the panel where a thumb reaches it.
            The auto margins do that rather than justify-*, so each part can be
            placed independently.

            On desktop there is no thumb to reach with, and a button stranded
            at the foot of a tall viewport reads as unrelated to the headline —
            so md: collapses the text and the button back into one centred
            group while the mark stays in its own top row. */}
        <div className="relative flex flex-1 flex-col px-5 py-6 md:py-14">
          <HeroLogo />

          <div className="flex flex-1 flex-col items-center gap-6 text-center">
            <div className="my-auto flex max-w-3xl flex-col gap-4 md:mb-0 md:mt-auto">
              <h1 className="text-balance text-3xl font-bold tracking-tight text-foreground sm:text-3xl md:text-4xl">
                <span className="block">Fragen stellen.</span>
                <span className="block">Politik verstehen.</span>
                <span className="block">Informiert wählen.</span>
              </h1>

              {/* An h2 rather than a p: now that the h1 is a short claim, this
                  line carries the page's keywords and reads as the hero's
                  subhead. Styled down to the supporting sentence it is — the
                  page still has exactly one h1, directly above it. */}
              <h2 className="text-pretty text-base font-normal text-muted-foreground md:text-lg">
                Welche Partei passt zu dir? Vergleiche Parteien, belegt durch
                Plenarprotokolle, namentliche Abstimmungen und Wahlprogramme.
              </h2>
            </div>

            {featuredElection && (
              <div className="flex w-full flex-col items-center gap-2 md:mb-auto">
                <p className="text-balance font-medium text-foreground">
                  {isUpcomingElection(featuredElection)
                    ? 'Nächste Wahl'
                    : 'Letzte Wahl'}
                  : {featuredElection.name}
                </p>

                {featuredDate && (
                  <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <CalendarIcon
                      className="size-4 shrink-0"
                      aria-hidden="true"
                    />
                    {featuredDate}
                  </p>
                )}

                <div className="mt-2 flex w-full justify-center">
                  <HeroCta context={featuredElection} />
                </div>
              </div>
            )}
          </div>
        </div>

        <ScrollCue href={`#${firstSectionAnchor}`} />
      </section>

      {hasOtherElections && (
        <LandingSection
          id={ELECTIONS_ANCHOR}
          title="Andere Wahlen auf wahl.chat"
        >
          <ElectionLinks upcoming={otherUpcoming} past={otherPast} />
        </LandingSection>
      )}

      {!IS_EMBEDDED && (
        <LandingSection className="py-8 md:py-10">
          <div className="mx-auto flex max-w-3xl flex-col gap-10">
            <KnownFrom />
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
