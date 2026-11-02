import { Card } from '@/components/ui/card';
import { resolveLocale } from '@/lib/seo';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const t = await getTranslations({ locale, namespace: 'meta.donate' });
  return {
    title: t('title'),
    description: t('description'),
    robots: 'noindex',
  };
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <section className="container flex h-full flex-col items-center justify-center py-4">
      <Card className="w-full max-w-lg border-0 md:border">{children}</Card>
    </section>
  );
}

export default Layout;
