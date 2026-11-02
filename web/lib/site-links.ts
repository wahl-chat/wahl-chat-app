import { PRESS_LINK } from '@/lib/contact-config';
import type { Messages } from 'next-intl';

export type SiteLink = {
  href: string;
  /** Key in the `nav` message namespace. */
  label: keyof Messages['nav'];
  /** Placeholder values for the label, e.g. an election's name. */
  values?: Record<string, string>;
  /** Opens in a new tab and needs rel="noopener noreferrer". */
  external?: boolean;
};

export const GITHUB_LINK = 'https://github.com/wahl-chat';

/**
 * Every site-wide link, named once.
 *
 * Both footers read from here, so the chat footer and the landing footer
 * cannot drift apart in label or destination. Labels are `nav` message keys,
 * rendered with `useTranslations('nav')`.
 *
 * Quellen is missing on purpose: it is per-election, and a bare /sources is a
 * geo-IP redirect. Build it with sourcesLink(contextId) instead.
 */
export const SITE_LINKS = {
  howTo: { href: '/how-to', label: 'howTo' },
  donate: { href: '/donate', label: 'donate' },
  aboutUs: { href: '/about-us', label: 'aboutUs' },
  github: { href: GITHUB_LINK, label: 'github', external: true },
  press: { href: PRESS_LINK, label: 'press', external: true },
  imprint: { href: '/impressum', label: 'imprint' },
  privacy: { href: '/datenschutz', label: 'privacy' },
} satisfies Record<string, SiteLink>;

export function sourcesLink(contextId: string): SiteLink {
  return { href: `/${contextId}/sources`, label: 'sources' };
}
