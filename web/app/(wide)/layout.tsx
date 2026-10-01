import DailyHeader from '@/components/daily/daily-header';
import Footer from '@/components/footer';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { cn } from '@/lib/utils';
/** Header + footer shell like (with-header), wide enough for two-column
 * feeds, and the home of the feed's editorial theme. */
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={cn(
        DAILY_THEME_CLASSES,
        'relative flex w-full flex-col bg-[var(--daily-canvas)]',
      )}
    >
      <DailyHeader />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-5xl grow px-4 pb-16 md:px-6">
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default Layout;
