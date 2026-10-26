import { Card } from '@/components/ui/card';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Spenden',
  description:
    'Unterstütze wahl.chat mit einer Spende – hilf uns, laufende Kosten für die KI zu decken.',
  robots: 'noindex',
};

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <section className="container flex h-full flex-col items-center justify-center py-4">
      <Card className="w-full max-w-lg border-0 md:border">{children}</Card>
    </section>
  );
}

export default Layout;
