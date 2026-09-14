import { PRESS_LINK } from '@/lib/contact-config';

export type SiteLink = {
  href: string;
  label: string;
  /** Opens in a new tab and needs rel="noopener noreferrer". */
  external?: boolean;
};

export const GITHUB_LINK = 'https://github.com/wahl-chat';

/**
 * Every site-wide link, named once.
 *
 * Both footers read from here, so the chat footer and the landing footer
 * cannot drift apart in label or destination.
 *
 * Quellen is missing on purpose: it is per-election, and a bare /sources is a
 * geo-IP redirect. Build it with sourcesLink(contextId) instead.
 */
export const SITE_LINKS = {
  howTo: { href: '/how-to', label: 'Anleitung' },
  donate: { href: '/donate', label: 'Spenden' },
  aboutUs: { href: '/about-us', label: 'Über uns' },
  github: { href: GITHUB_LINK, label: 'GitHub', external: true },
  press: { href: PRESS_LINK, label: 'Presse', external: true },
  imprint: { href: '/impressum', label: 'Impressum' },
  privacy: { href: '/datenschutz', label: 'Datenschutz' },
} satisfies Record<string, SiteLink>;

export function sourcesLink(contextId: string): SiteLink {
  return { href: `/${contextId}/sources`, label: 'Quellen' };
}
