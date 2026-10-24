'use client';

import { FEED_STRINGS, type FeedStrings, intlLocale } from '@/lib/daily/i18n';
import type { FeedLocale } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { type ReactNode, createContext, useContext } from 'react';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

const FeedLocaleContext = createContext<FeedLocale>('de');

export function FeedLocaleProvider({
  locale,
  children,
}: {
  locale: FeedLocale;
  children: ReactNode;
}) {
  return (
    <FeedLocaleContext.Provider value={locale}>
      {children}
    </FeedLocaleContext.Provider>
  );
}

export function useFeedLocale(): {
  locale: FeedLocale;
  /** BCP 47 tag for `Intl` formatters. */
  intl: string;
  t: FeedStrings;
} {
  const locale = useContext(FeedLocaleContext);
  return { locale, intl: intlLocale(locale), t: FEED_STRINGS[locale] };
}

const LABELS: Record<FeedLocale, { short: string; name: string }> = {
  de: { short: 'DE', name: 'Deutsch' },
  en: { short: 'EN', name: 'English' },
};

/** "DE | EN": switches the feed's language in place. */
export function LanguageToggle({
  onChange,
}: {
  onChange: (locale: FeedLocale) => void;
}) {
  const { locale, t } = useFeedLocale();
  return (
    <fieldset className="flex h-14 shrink-0 items-center rounded-[10px] border border-[var(--daily-border)] p-1">
      <legend className="sr-only">{t.language}</legend>
      {(Object.keys(LABELS) as FeedLocale[]).map((option) => (
        <button
          key={option}
          type="button"
          lang={option}
          aria-pressed={locale === option}
          aria-label={LABELS[option].name}
          onClick={() => onChange(option)}
          className={cn(
            FOCUS_RING,
            'h-full min-w-11 rounded-md px-2 text-[15px] font-semibold transition-colors',
            locale === option
              ? 'bg-[var(--daily-ink)] text-[var(--daily-canvas)]'
              : cn(MUTED_TEXT, 'hover:text-[var(--daily-ink)]'),
          )}
        >
          {LABELS[option].short}
        </button>
      ))}
    </fieldset>
  );
}
