import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import Logo from '@/components/chat/logo';
import { SITE_LINKS } from '@/lib/site-links';
import { IS_EMBEDDED, cn } from '@/lib/utils';
import { MessageCircleIcon } from 'lucide-react';
import Link from 'next/link';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';
import WeeklySignupButton from './weekly-signup-button';

/**
 * The site header on the feed's column width, so the logo and the login
 * button line up with the cards: "wahl.chat / News", the product's name next
 * to the brand. The Chat link opens the current election's page.
 * "Meine Woche" asks readers to sign up for the weekly digest.
 * Anleitung and Spenden live in the footer.
 */
function DailyHeader({ chatHref }: { chatHref: string }) {
  return (
    <header className="sticky top-0 z-30 h-header border-b border-[var(--daily-border)] bg-[var(--daily-canvas)]">
      <div className="mx-auto flex size-full max-w-screen-sm items-center justify-between gap-2 px-4 sm:gap-4">
        <Link
          href="/"
          aria-label="wahl.chat News"
          className={cn(
            FOCUS_RING,
            'flex items-center gap-2 rounded-md text-[var(--daily-ink)] sm:gap-3',
          )}
        >
          <Logo className="size-10 sm:size-12" />
          <span
            aria-hidden
            className="h-8 w-[3px] skew-x-[-18deg] rounded-full bg-[var(--daily-border)]"
          />
          <span
            aria-hidden
            className="text-[22px] font-bold leading-none sm:text-[28px]"
          >
            News
          </span>
        </Link>

        {!IS_EMBEDDED && (
          <nav className="flex items-center gap-1 sm:gap-2">
            <Link
              href={chatHref}
              className={cn(
                FOCUS_RING,
                'flex min-h-10 items-center gap-1.5 rounded-lg px-2 text-[15px] transition-colors hover:text-[var(--daily-ink)] sm:gap-2 sm:px-3 sm:text-[17px]',
                MUTED_TEXT,
              )}
            >
              <MessageCircleIcon className="size-4" aria-hidden />
              {SITE_LINKS.chat.label}
            </Link>
            {/* The root layout seeds the auth state from the session, so a
                signed-in reader gets the avatar on first paint. */}
            <LoginButton
              purpose="briefings"
              noUserChildren={<WeeklySignupButton />}
              userChildren={<UserAvatar />}
            />
          </nav>
        )}
      </div>
    </header>
  );
}

export default DailyHeader;
