import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Swiper',
  description: 'Wahl Swiper - Finde heraus, welche Partei zu dir passt.',
  openGraph: {
    title: 'Swiper',
    description: 'Wahl Swiper - Finde heraus, welche Partei zu dir passt.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Swiper',
    description: 'Wahl Swiper - Finde heraus, welche Partei zu dir passt.',
  },
};

function Layout({ children }: { children: React.ReactNode }) {
  return children;
}

export default Layout;
