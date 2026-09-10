'use client';

import { SITE_LINKS, sourcesLink } from '@/lib/site-links';
import Link from 'next/link';
import Logo from './chat/logo';
import { ThemeModeToggle } from './chat/theme-mode-toggle';
import FeedbackDialog from './feedback-dialog';
import { useCurrentContext } from './providers/context-provider';

function Footer() {
  const context = useCurrentContext({ optional: true });
  // Outside a ContextProvider there is no election to point at; middleware
  // resolves the bare path by region.
  const sources = context
    ? sourcesLink(context.context_id)
    : { href: '/sources', label: 'Quellen' };

  return (
    <footer className="flex h-footer w-full flex-col items-center justify-center gap-4 border-t p-4 text-xs text-muted-foreground md:flex-row">
      <Logo className="size-5" variant="small" />

      <section className="flex grow flex-wrap items-center justify-center gap-2 underline md:justify-end">
        <Link href={SITE_LINKS.howTo.href}>{SITE_LINKS.howTo.label}</Link>
        <Link href={SITE_LINKS.donate.href}>{SITE_LINKS.donate.label}</Link>
        <Link href={SITE_LINKS.aboutUs.href}>{SITE_LINKS.aboutUs.label}</Link>
        <Link href={sources.href}>{sources.label}</Link>
        <Link href={SITE_LINKS.press.href} target="_blank">
          {SITE_LINKS.press.label}
        </Link>
        <FeedbackDialog>
          <button type="button">Feedback</button>
        </FeedbackDialog>
        <Link href={SITE_LINKS.imprint.href}>{SITE_LINKS.imprint.label}</Link>
        <Link href={SITE_LINKS.privacy.href}>{SITE_LINKS.privacy.label}</Link>
      </section>

      <ThemeModeToggle />
    </footer>
  );
}

export default Footer;
