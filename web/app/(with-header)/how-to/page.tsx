import ContactCard from '@/components/home/contact-card';
import GitHubCard from '@/components/home/github-card';
import SupportUsCard from '@/components/home/support-us-card';
import HowTo from '@/components/how-to';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'So funktioniert wahl.chat',
  description:
    'Erfahre, wie du wahl.chat nutzen kannst: den Parlaments-Feed lesen, im Chat nachfragen, Parteien vergleichen und quellengestützte Antworten erhalten.',
  alternates: {
    canonical: '/how-to',
  },
};

/** The how-to, plus the ways to support and reach us: the one page about
 * wahl.chat itself rather than the feed or an election. */
function HowToPage() {
  return (
    <>
      <h1 className="my-4 text-xl font-bold md:text-2xl">
        So funktioniert <span className="underline">wahl.chat</span>
      </h1>
      <HowTo />
      <section
        aria-labelledby="about-wahl-chat"
        className="mt-10 flex flex-col gap-4"
      >
        <h2 id="about-wahl-chat" className="text-lg font-bold">
          Über <span className="underline">wahl.chat</span>
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          <SupportUsCard titleAs="h3" />
          <ContactCard titleAs="h3" />
          <GitHubCard titleAs="h3" fullWidth />
        </div>
      </section>
    </>
  );
}

export default HowToPage;
