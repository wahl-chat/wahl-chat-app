import Footer from '@/components/footer';
import Header from '@/components/header';
import { Button } from '@/components/ui/button';
import { SearchXIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Seite nicht gefunden',
};

/**
 * Every unknown path ends here, including the ones the /[contextId] catch-all
 * rejects. It sits outside any route group, so it brings its own header and
 * footer rather than inheriting them.
 */
function NotFound() {
  return (
    <div className="relative flex w-full flex-col">
      <Header />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-xl grow px-4 pb-8 md:px-0">
        <section className="mx-auto flex h-full max-w-lg flex-col items-center justify-center space-y-4 p-4 pt-16 text-center">
          <SearchXIcon className="size-12" aria-hidden="true" />
          <h1 className="text-2xl font-bold">Seite nicht gefunden</h1>
          <p className="text-muted-foreground">
            Diese Seite gibt es nicht oder nicht mehr. Auf der Startseite
            findest du, was gerade im Bundestag passiert, und den Weg zum Chat.
          </p>
          <Button asChild>
            <Link href="/">Zur Startseite</Link>
          </Button>
        </section>
      </main>
      <Footer />
    </div>
  );
}

export default NotFound;
