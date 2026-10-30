import HowTo from '@/components/how-to';
import { DEFAULT_LOCALE, isLocale } from '@/i18n/locales';
import { localeAlternates } from '@/lib/seo';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';

type Props = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale: requested } = await params;
  const locale = isLocale(requested) ? requested : DEFAULT_LOCALE;
  const t = await getTranslations({ locale, namespace: 'howTo' });

  return {
    title: t('meta.title'),
    description: t('meta.description'),
    alternates: localeAlternates('/how-to', locale),
  };
}

async function HowToPage() {
  const t = await getTranslations('howTo');

  return (
    <>
      <h1 className="mb-2 mt-4 text-xl font-bold md:text-2xl">
        {t.rich('heading', {
          underline: (chunks) => <span className="underline">{chunks}</span>,
        })}
      </h1>
      <HowTo />
    </>
  );
}

export default HowToPage;
