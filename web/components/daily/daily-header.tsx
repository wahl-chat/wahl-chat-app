import Logo from '@/components/chat/logo';
import { LocaleSwitcher } from '@/components/locale/locale-switcher';
import { Link } from '@/i18n/navigation';
import { SITE_LINKS } from '@/lib/site-links';
import { IS_EMBEDDED, cn } from '@/lib/utils';
import { HeartIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

/**
 * The site header on the feed's column width, so the logo and the donation
 * button line up with the cards. The feed's own inputs lead into the chat.
 */
function DailyHeader() {
  const t = useTranslations('header');
  return (
    <header className="sticky top-0 z-30 h-header border-b border-[var(--daily-border)] bg-[var(--daily-canvas)]">
      <div className="mx-auto flex size-full max-w-screen-sm items-center justify-between gap-3 px-4 sm:gap-4">
        <Link
          href="/"
          aria-label={t('home')}
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
                'flex min-h-10 items-center rounded-lg px-2 text-[15px] sm:px-3 sm:text-[17px]',
                MUTED_TEXT,
              )}
            >
              {t('guide')}
            </Link>
            <LocaleSwitcher
              className={cn(
                FOCUS_RING,
                'gap-1.5 px-2 sm:gap-2 sm:px-3 border-[var(--daily-border)] text-[var(--daily-muted)] hover:text-[var(--daily-ink)]',
              )}
            />
            <Link
              href={SITE_LINKS.donate.href}
              className={cn(
                FOCUS_RING,
                'flex h-10 items-center gap-2 rounded-lg bg-[var(--daily-ink)] px-3 text-[15px] sm:px-4 font-semibold text-[var(--daily-canvas)]',
              )}
            >
              <HeartIcon className="size-4" aria-hidden />
              {t('donate')}
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}

export default DailyHeader;
