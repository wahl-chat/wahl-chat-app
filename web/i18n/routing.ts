import { defineRouting } from 'next-intl/routing';
import { DEFAULT_LOCALE, LOCALES } from './locales';

export const routing = defineRouting({
  locales: LOCALES,
  defaultLocale: DEFAULT_LOCALE,
  // German keeps its URLs (wahl.chat/…); every other language is prefixed
  // (wahl.chat/en/…), so links and search results stay language-specific.
  localePrefix: 'as-needed',
  // No Accept-Language guessing: many German readers run English browsers,
  // and / must serve the same page to crawlers and visitors. A visitor's own
  // choice is remembered by the LOCALE_COOKIE the middleware honours.
  localeDetection: false,
});
