import Logo from '@/components/chat/logo';
import { SITE_LINKS } from '@/lib/site-links';
import { IS_EMBEDDED, cn } from '@/lib/utils';
import { HeartIcon } from 'lucide-react';
import Link from 'next/link';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

/**
 * The site header on the feed's column width, so the logo and the donation
 * button line up with the cards. The feed's own inputs lead into the chat.
 */
function DailyHeader() {
  return (
    <header className="sticky top-0 z-30 h-header border-b border-[var(--daily-border)] bg-[var(--daily-canvas)]">
      <div className="mx-auto flex size-full max-w-screen-sm items-center justify-between gap-4 px-4">
        <Link
          href="/"
          aria-label="wahl.chat Startseite"
          className={cn(FOCUS_RING, 'rounded-md')}
        >
          <Logo className="size-12 text-[var(--daily-ink)]" />
        </Link>

        {!IS_EMBEDDED && (
          <nav className="flex items-center gap-2">
            <Link
              href="/how-to"
              className={cn(
                FOCUS_RING,
                'flex min-h-10 items-center rounded-lg px-3 text-[17px]',
                MUTED_TEXT,
              )}
            >
              Anleitung
            </Link>
            <Link
              href={SITE_LINKS.donate.href}
              className={cn(
                FOCUS_RING,
                'flex h-10 items-center gap-2 rounded-lg bg-[var(--daily-ink)] px-4 text-[15px] font-semibold text-[var(--daily-canvas)]',
              )}
            >
              <HeartIcon className="size-4" aria-hidden />
              {SITE_LINKS.donate.label}
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}

export default DailyHeader;
