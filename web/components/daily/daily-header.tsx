import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import Logo from '@/components/chat/logo';
import { SITE_LINKS } from '@/lib/site-links';
import { IS_EMBEDDED, cn } from '@/lib/utils';
import { LogInIcon, MessageCircleIcon } from 'lucide-react';
import Link from 'next/link';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';

/**
 * The site header on the feed's column width, so the logo and the login
 * button line up with the cards. The feed's own inputs lead into the chat;
 * the header's Chat link is the way back to the classic election chat.
 * Anleitung and Spenden live in the footer.
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
              href={SITE_LINKS.chat.href}
              className={cn(
                FOCUS_RING,
                'flex min-h-10 items-center gap-2 rounded-lg px-3 text-[17px] transition-colors hover:text-[var(--daily-ink)]',
                MUTED_TEXT,
              )}
            >
              <MessageCircleIcon className="size-4" aria-hidden />
              {SITE_LINKS.chat.label}
            </Link>
            {/* The root layout seeds the auth state from the session, so a
                signed-in reader gets the avatar on first paint. */}
            <LoginButton
              noUserChildren={
                <button
                  type="button"
                  className={cn(
                    FOCUS_RING,
                    'flex h-10 items-center gap-2 rounded-lg bg-[var(--daily-ink)] px-4 text-[15px] font-semibold text-[var(--daily-canvas)]',
                  )}
                >
                  <LogInIcon className="size-4" aria-hidden />
                  Anmelden
                </button>
              }
              userChildren={<UserAvatar />}
            />
          </nav>
        )}
      </div>
    </header>
  );
}

export default DailyHeader;
