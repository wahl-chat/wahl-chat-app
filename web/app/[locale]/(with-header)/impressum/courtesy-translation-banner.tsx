import type { Locale } from '@/i18n/locales';
import { Link } from '@/i18n/navigation';
import { getTranslations } from 'next-intl/server';

type Props = {
  locale: Locale;
  /** The page's path without a locale prefix, e.g. `/impressum`. */
  href: string;
};

/** Shown above a translated legal page: only the German text binds, so the
 * reader is pointed at it. */
export async function CourtesyTranslationBanner({ locale, href }: Props) {
  const t = await getTranslations({ locale, namespace: 'legal' });

  return (
    <aside className="mt-6 rounded-md border bg-muted p-4 text-sm">
      <p>{t('translationNotice')}</p>
      <Link href={href} locale="de" hrefLang="de" className="underline">
        {t('readGermanVersion')}
      </Link>
    </aside>
  );
}
