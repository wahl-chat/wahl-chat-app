import Footer from '@/components/footer';
import WahlSwiperHeader from '@/components/wahl-swiper/wahl-swiper-header';
import type { Locale } from '@/i18n/locales';
import { getContext } from '@/lib/firebase/firebase-server';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; contextId: string }>;
}): Promise<Metadata> {
  const { locale, contextId } = await params;
  // The root layout has already rejected unknown locales with a 404.
  const t = await getTranslations({
    locale: locale as Locale,
    namespace: 'swiper.meta',
  });
  const context = await getContext(contextId);

  if (!context) {
    return { title: t('fallbackTitle') };
  }

  const title = t('title', { context: context.name });
  const description = t('description', { context: context.name });

  return {
    title,
    description,
    robots: 'noindex',
    openGraph: {
      title,
      description,
      url: `https://wahl.chat/${contextId}/swiper`,
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
  };
}

async function Layout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ contextId: string }>;
}) {
  const { contextId } = await params;

  return (
    <div className="relative flex w-full flex-col">
      <WahlSwiperHeader contextId={contextId} />
      <main className="mx-auto min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full max-w-xl grow px-4 pb-8 md:px-0">
        {children}
      </main>
      <Footer />
    </div>
  );
}

export default Layout;
