/**
 * The one list of languages the site speaks. Routing, the language selector,
 * date formatting, hreflang and the sitemap all read from here, so adding a
 * language starts with one entry below (plus its flag in
 * `components/locale/flags.tsx` and its `messages/{code}.json`).
 */

export const LOCALES = ['de', 'en'] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = 'de';

/** Set by the language selector; the middleware sends prefix-less visits to
 * the chosen language. */
export const LOCALE_COOKIE = 'NEXT_LOCALE';

type LocaleInfo = {
  /** The language's own name, shown in the selector. */
  endonym: string;
  /** Shown next to the flag in the selector's trigger. */
  short: string;
  /** BCP 47 tag for `Intl` date and number formatting. */
  intl: string;
  openGraph: string;
};

export const LOCALE_INFO: Record<Locale, LocaleInfo> = {
  de: { endonym: 'Deutsch', short: 'DE', intl: 'de-DE', openGraph: 'de_DE' },
  en: { endonym: 'English', short: 'EN', intl: 'en-GB', openGraph: 'en_GB' },
};

export function isLocale(value: unknown): value is Locale {
  return LOCALES.includes(value as Locale);
}
