import DailyHeader from '@/components/daily/daily-header';
import Footer from '@/components/footer';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { getStimmtsStatus } from '@/lib/firebase/firebase-server';
import { cn } from '@/lib/utils';

/** Header + footer shell like (with-header): one centred column that reads
 * as the phone layout on desktop too, and the home of the feed's theme. */
async function Layout({ children }: { children: React.ReactNode }) {
  const stimmtsStatus = await getStimmtsStatus();
  return (
    <div
      className={cn(
        DAILY_THEME_CLASSES,
        'relative flex w-full flex-col bg-[var(--daily-canvas)]',
      )}
    >
      <DailyHeader stimmtsEnabled={stimmtsStatus.enabled} />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-screen-sm grow px-4 pb-6">
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default Layout;
