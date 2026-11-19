import { describe, expect, it } from 'bun:test';
import type { Context } from '@/lib/firebase/firebase.types';
import {
  buildContextCanonical,
  buildContextJsonLd,
  buildContextMetadata,
  localeAlternates,
  localizedUrl,
} from './seo';

const context = {
  context_id: 'landtagswahl-berlin-2026',
  name: 'Abgeordnetenhauswahl Berlin 2026',
  location_name: 'Berlin',
  date: new Date('2026-09-20T00:00:00Z'),
} as unknown as Context;

describe('localeAlternates', () => {
  it('points the canonical at the page’s own language', () => {
    expect(localeAlternates('/about-us', 'de').canonical).toBe('/about-us');
    expect(localeAlternates('/about-us', 'en').canonical).toBe('/en/about-us');
  });

  it('lists every language plus a German x-default', () => {
    expect(localeAlternates('/', 'en').languages).toEqual({
      de: '/',
      en: '/en',
      'x-default': '/',
    });
  });
});

describe('localizedUrl', () => {
  it('keeps the bare origin for the German home page', () => {
    expect(localizedUrl('/', 'de')).toBe('https://wahl.chat');
    expect(localizedUrl('/', 'en')).toBe('https://wahl.chat/en');
    expect(localizedUrl('/chat', 'en')).toBe('https://wahl.chat/en/chat');
  });
});

describe('context metadata', () => {
  it('defaults to German so existing callers are unchanged', () => {
    const metadata = buildContextMetadata(context);
    expect(metadata.title).toBe(
      'Abgeordnetenhauswahl Berlin 2026 – Parteipositionen im Chat vergleichen',
    );
    expect(metadata.description).toContain('am 20. September 2026');
    expect(
      buildContextCanonical(context.context_id).alternates?.canonical,
    ).toBe('/landtagswahl-berlin-2026');
  });

  it('translates title, description and URLs for English', () => {
    const metadata = buildContextMetadata(context, {
      path: 'sources',
      pageSuffix: 'Sources',
      locale: 'en',
    });
    expect(metadata.title).toBe('Sources – Abgeordnetenhauswahl Berlin 2026');
    expect(metadata.description).toContain('on 20 September 2026');
    expect(metadata.openGraph?.url).toBe(
      'https://wahl.chat/en/landtagswahl-berlin-2026/sources',
    );

    const jsonLd = buildContextJsonLd(context, undefined, 'en');
    expect(jsonLd.url).toBe('https://wahl.chat/en/landtagswahl-berlin-2026');
    expect(jsonLd.inLanguage).toBe('en');
  });
});
