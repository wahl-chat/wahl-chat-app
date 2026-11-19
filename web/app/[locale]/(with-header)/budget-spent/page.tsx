import DonationDialog from '@/components/donation-dialog';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { resolveLocale } from '@/lib/seo';
import { BadgeEuroIcon, HeartHandshakeIcon } from 'lucide-react';
import type { Metadata } from 'next';
import { useTranslations } from 'next-intl';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const t = await getTranslations({ locale, namespace: 'meta.budgetSpent' });
  return {
    title: t('title'),
    description: t('description'),
    robots: 'noindex',
  };
}

function BudgetSpent() {
  const t = useTranslations('donate.budgetSpent');
  const tNav = useTranslations('nav');

  return (
    <section className="mx-auto flex h-full max-w-lg flex-col items-center justify-center space-y-4 p-4 text-center">
      <BadgeEuroIcon className="size-12" />
      <h1 className="text-2xl font-bold">{t('title')}</h1>
      <p>{t('explanation')}</p>
      <p>{t('invitation')}</p>
      <div className="flex justify-center gap-2">
        <DonationDialog>
          <Button>
            <HeartHandshakeIcon />
            {t('supportUs')}
          </Button>
        </DonationDialog>
        <Button variant="outline" asChild>
          <Link href="/about-us">{tNav('aboutUs')}</Link>
        </Button>
      </div>
    </section>
  );
}

export default BudgetSpent;
