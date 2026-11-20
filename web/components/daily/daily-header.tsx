import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import Logo from '@/components/chat/logo';
import MobileNavbar from '@/components/navbar/mobile-navbar';
import { IS_EMBEDDED, cn } from '@/lib/utils';
import Link from 'next/link';
import { FOCUS_RING } from './card-styles';
import StimmtsHeaderIcon from './stimmts-header-icon';
import WeeklySignupButton from './weekly-signup-button';

/**
 * The site header on the feed's column width, so the logo and the login
 * button line up with the cards: "wahl.chat / News", the product's name next
 * to the brand. "Meine Woche" asks readers to sign up for the weekly digest.
 * Players of Stimmt's? also get its icon, which leads back to their result,
 * while the game is switched on (`stimmtsEnabled`, the server's reading of the
 * switch). The rest (Chat, Anleitung, Spenden, Feedback) sits in the menu,
 * which the feed shows at every width since its column reads as the phone
 * layout.
 */
function DailyHeader({ stimmtsEnabled }: { stimmtsEnabled: boolean }) {
  return (
    <header className="daily-header sticky top-0 z-30 h-header border-b border-[var(--daily-border)] bg-[var(--daily-canvas)]">
      <div className="mx-auto flex size-full max-w-screen-sm items-center justify-between gap-2 px-4 sm:gap-4">
        <Link
          href="/"
          aria-label="wahl.chat News"
          className={cn(
            FOCUS_RING,
            'flex items-center gap-2 rounded-md text-[var(--daily-ink)] sm:gap-3',
          )}
        >
          <Logo className="size-10 max-[380px]:size-9 sm:size-12" />
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
            <StimmtsHeaderIcon serverEnabled={stimmtsEnabled} />
            {/* The root layout seeds the auth state from the session, so a
                signed-in reader gets the avatar on first paint. */}
            <LoginButton
              purpose="briefings"
              noUserChildren={<WeeklySignupButton />}
              userChildren={<UserAvatar />}
            />
            <MobileNavbar alwaysVisible />
          </nav>
        )}
      </div>
    </header>
  );
}

export default DailyHeader;
