import { DEFAULT_LOCALE, type Locale, isLocale } from '@/i18n/locales';
import deChat from '@/messages/de/chat.json';
import enChat from '@/messages/en/chat.json';
import { createTranslator } from 'next-intl';

/**
 * Store actions run outside React, so they cannot reach `useTranslations`.
 * Their toasts read the `chat.store` catalog through a standalone translator
 * instead, in the language the page was rendered in (`<html lang>`, set from
 * the route's locale).
 */

const CATALOGS: Record<Locale, { chat: typeof deChat }> = {
  de: { chat: deChat },
  en: { chat: enChat },
};

export type StoreMessageKey = keyof typeof deChat.store;

function currentLocale(): Locale {
  if (typeof document === 'undefined') {
    return DEFAULT_LOCALE;
  }
  const lang = document.documentElement.lang;
  return isLocale(lang) ? lang : DEFAULT_LOCALE;
}

export function storeMessage(key: StoreMessageKey): string {
  const locale = currentLocale();
  const t = createTranslator({
    locale,
    messages: CATALOGS[locale],
    namespace: 'chat.store',
  });
  return t(key);
}
