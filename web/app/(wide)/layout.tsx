import DailyHeader from '@/components/daily/daily-header';
import Footer from '@/components/footer';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { chatElection } from '@/lib/elections';
import { getContexts } from '@/lib/firebase/firebase-server';
import { SITE_LINKS } from '@/lib/site-links';
import { cn } from '@/lib/utils';

/** Header + footer shell like (with-header): one centred column that reads
 * as the phone layout on desktop too, and the home of the feed's theme. */
async function Layout({ children }: { children: React.ReactNode }) {
  const election = chatElection(await getContexts());
  // The election's page, which leads into its chat, rather than a session
  // started straight away.
  const chatHref = election ? `/${election.context_id}` : SITE_LINKS.chat.href;
  return (
    <div
      className={cn(
        DAILY_THEME_CLASSES,
        'relative flex w-full flex-col bg-[var(--daily-canvas)]',
      )}
    >
      <DailyHeader chatHref={chatHref} />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-screen-sm grow px-4 pb-6">
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default Layout;
