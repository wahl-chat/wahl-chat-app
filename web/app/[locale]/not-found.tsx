import Footer from '@/components/footer';
import Header from '@/components/header';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { SearchXIcon } from 'lucide-react';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('errors.notFound');
  return { title: t('title') };
}

/**
 * Every unknown path ends here: the ones the /[contextId] catch-all rejects
 * and, through `[...rest]`, every deeper one. It sits outside any route
 * group, so it brings its own header and footer rather than inheriting them.
 */
async function NotFound() {
  const t = await getTranslations('errors.notFound');
  return (
    <div className="relative flex w-full flex-col">
      <Header />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-xl grow px-4 pb-8 md:px-0">
        <section className="mx-auto flex h-full max-w-lg flex-col items-center justify-center space-y-4 p-4 pt-16 text-center">
          <SearchXIcon className="size-12" aria-hidden="true" />
          <h1 className="text-2xl font-bold">{t('title')}</h1>
          <p className="text-muted-foreground">{t('description')}</p>
          <Button asChild>
            <Link href="/">{t('home')}</Link>
          </Button>
        </section>
      </main>
      <Footer />
    </div>
  );
}

export default NotFound;
