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

function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

export default Layout;
