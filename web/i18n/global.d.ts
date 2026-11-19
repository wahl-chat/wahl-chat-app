import type de from '../messages/de';
import type { Locale } from './locales';

// German is the source catalog: every key used with `t()` must exist there,
// so a typo or a missing message fails the type check, not the reader.
declare module 'next-intl' {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof de;
  }
}
