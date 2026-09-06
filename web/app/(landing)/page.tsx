import Logo from '@/components/chat/logo';
import { ContextIcon } from '@/components/context-icon';
import BrandBlurBackdrop from '@/components/home/brand-blur-backdrop';
import ElectionLinks from '@/components/home/election-links';
import JsonLd from '@/components/seo/json-ld';
import { Button } from '@/components/ui/button';
import { isUpcomingElection, splitElectionsByDate } from '@/lib/elections';
import { getContexts } from '@/lib/firebase/firebase-server';
import { BASE_URL, WEBSITE_ID, productionRobots } from '@/lib/seo';
import { formatGermanDate } from '@/lib/utils';
import { ArrowRightIcon, CalendarIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

// The featured election is derived from the context dates, so it rolls over on
// its own once the current one concludes, and the output does not depend on the
// requester — crawlers and visitors get the same page, which the geo redirect
// this replaced could not promise. Freshness comes from the context read, which
// is cached and busted by tag on seed; a page-level revalidate would pin an
// empty list into a shell instead.
export const dynamic = 'force-dynamic';

const TITLE =
  'wahl.chat – Parteipositionen zur Wahl im Chat vergleichen, mit Quellen';
const DESCRIPTION =
  'Stelle den Parteien deine eigenen Fragen und vergleiche ihre Positionen zu Bundestags-, Landtags- und Kommunalwahlen – belegt durch Plenarprotokolle, namentliche Abstimmungen und Wahlprogramme.';

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

// Everything a visitor still needs to reach from a page with no footer.
// Impressum and Datenschutz are not optional: German law requires them to stay
// one click away from every page.
const PANEL_LINKS = [
  { href: '/how-to', label: 'Anleitung' },
  { href: '/about-us', label: 'Über uns' },
  { href: '/impressum', label: 'Impressum' },
  { href: '/datenschutz', label: 'Datenschutz' },
];

export default async function Landing() {
  const contexts = await getContexts();
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

  // Mirrors the links in the panel: same set, same order, so the structured
  // data and the crawlable markup cannot drift apart.
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

      {/* One full-viewport panel. dvh rather than vh so the mobile browser
          chrome collapsing does not leave the panel taller than the screen. */}
      <section className="relative flex min-h-dvh w-full flex-col overflow-hidden">
        <BrandBlurBackdrop />

        <div className="relative flex flex-1 flex-col items-center justify-center gap-5 px-5 py-8 text-center md:gap-6 md:py-14">
          <Logo variant="large" className="h-8 w-auto md:h-10" />

          <div className="flex max-w-3xl flex-col gap-4">
            <h1 className="text-balance text-2xl font-bold tracking-tight text-foreground sm:text-3xl md:text-4xl">
              Mit wahl.chat Parteipositionen zur Wahl vergleichen: im Chat mit
              Quellen aus offiziellen Dokumenten.
            </h1>

            <p className="text-pretty text-sm text-muted-foreground sm:text-base md:text-lg">
              Individuelle Fragen, individuelle Antworten, belegt durch
              Plenarprotokolle, Mitschnitte aus dem Bundestag, namentliche
              Abstimmungen und Wahlprogramme.
            </p>
          </div>

          {featuredElection && (
            <div className="flex w-full flex-col items-center gap-2">
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
            </div>
          )}

          <ElectionLinks
            upcoming={upcoming}
            past={past}
            featuredId={featuredElection?.context_id}
          />
        </div>

        <nav
          aria-label="Weitere Seiten"
          className="relative flex flex-wrap items-center justify-center gap-x-4 gap-y-2 px-5 pb-6 text-xs md:pb-8 text-muted-foreground"
        >
          {PANEL_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="hover:underline">
              {link.label}
            </Link>
          ))}
        </nav>
      </section>
    </>
  );
}
