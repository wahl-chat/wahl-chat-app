import { Markdown } from '@/components/markdown';
import { DEFAULT_LOCALE, type Locale, isLocale } from '@/i18n/locales';
import { localeAlternates } from '@/lib/seo';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import { CourtesyTranslationBanner } from './courtesy-translation-banner';
import { IMPRESSUM_DE } from './impressum.de';
import { IMPRESSUM_EN } from './impressum.en';

const IMPRESSUM: Record<Locale, string> = {
  de: IMPRESSUM_DE,
  en: IMPRESSUM_EN,
};

type Props = {
  params: Promise<{ locale: string }>;
};

async function resolveLocale(params: Props['params']): Promise<Locale> {
  const { locale } = await params;
  return isLocale(locale) ? locale : DEFAULT_LOCALE;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await resolveLocale(params);
  const t = await getTranslations({ locale, namespace: 'legal' });

  return {
    title: t('impressum.title'),
    description: t('impressum.description'),
    robots: 'noindex',
    alternates: localeAlternates('/impressum', locale),
  };
}

async function Impressum({ params }: Props) {
  const locale = await resolveLocale(params);

  return (
    <div className="mx-auto w-full">
      {locale !== DEFAULT_LOCALE && (
        <CourtesyTranslationBanner locale={locale} href="/impressum" />
      )}
      <Markdown onReferenceClick={() => {}}>{IMPRESSUM[locale]}</Markdown>
    </div>
  );
}

export default Impressum;
