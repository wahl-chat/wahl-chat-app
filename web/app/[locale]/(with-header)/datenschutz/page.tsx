import { CourtesyTranslationBanner } from '@/app/[locale]/(with-header)/impressum/courtesy-translation-banner';
import { DEFAULT_LOCALE, type Locale, isLocale } from '@/i18n/locales';
import { localeAlternates } from '@/lib/seo';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import type { ComponentType } from 'react';
import { DatenschutzDe } from './content.de';
import { DatenschutzEn } from './content.en';

const DATENSCHUTZ: Record<Locale, ComponentType> = {
  de: DatenschutzDe,
  en: DatenschutzEn,
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
    title: t('datenschutz.title'),
    description: t('datenschutz.description'),
    robots: 'noindex',
    alternates: localeAlternates('/datenschutz', locale),
  };
}

async function Datenschutz({ params }: Props) {
  const locale = await resolveLocale(params);
  const Content = DATENSCHUTZ[locale];

  return (
    <>
      {locale !== DEFAULT_LOCALE && (
        <CourtesyTranslationBanner locale={locale} href="/datenschutz" />
      )}
      <Content />
    </>
  );
}

export default Datenschutz;
