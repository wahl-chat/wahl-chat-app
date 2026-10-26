import Footer from '@/components/footer';
import WahlSwiperHeader from '@/components/wahl-swiper/wahl-swiper-header';
import { getContext } from '@/lib/firebase/firebase-server';
import type { Metadata } from 'next';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ contextId: string }>;
}): Promise<Metadata> {
  const { contextId } = await params;
  const context = await getContext(contextId);

  if (!context) {
    return { title: 'Wahl-Swiper' };
  }

  const description = `Wahl-Swiper für ${context.name} – Finde heraus, welche Partei zu dir passt.`;

  return {
    title: `Wahl-Swiper – ${context.name}`,
    description,
    robots: 'noindex',
    openGraph: {
      title: `Wahl-Swiper – ${context.name}`,
      description,
      url: `https://wahl.chat/${contextId}/swiper`,
    },
    twitter: {
      card: 'summary_large_image',
      title: `Wahl-Swiper – ${context.name}`,
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
