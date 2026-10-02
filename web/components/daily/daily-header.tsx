import Logo from '@/components/chat/logo';
import MobileNavbar from '@/components/navbar/mobile-navbar';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { SITE_LINKS } from '@/lib/site-links';
import { IS_EMBEDDED, cn, getUserDetailsFromUser } from '@/lib/utils';
import { HeartIcon } from 'lucide-react';
import Link from 'next/link';
import { PRESSABLE } from './card-styles';
import DailyNavLink from './daily-nav-link';

const TABS = [
  { href: '/', label: 'Startseite' },
  { href: '/how-to', label: 'Anleitung' },
  { href: '/chat', label: 'Chat' },
];

/**
 * The site header in the feed's editorial style, on the same max-width and
 * gutters as the feed below it so the logo and the donation button line up
 * with the content's edges. Login stays reachable through the mobile menu.
 */
async function DailyHeader() {
  const user = !IS_EMBEDDED ? await getCurrentUser() : undefined;
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <header className="sticky top-0 z-30 h-header border-b-[3px] border-[var(--daily-ink)] bg-[var(--daily-canvas)]">
      <div className="relative mx-auto flex size-full max-w-5xl items-center justify-between gap-4 px-4 md:px-6">
        <Link href="/" aria-label="wahl.chat Startseite">
          <Logo className="size-12 text-[var(--daily-ink)] md:size-14" />
        </Link>

        {!IS_EMBEDDED && (
          <>
            <MobileNavbar userDetails={userDetails} />
            <nav className="hidden items-center gap-1 md:flex">
              {TABS.map((tab) => (
                <DailyNavLink key={tab.href} href={tab.href}>
                  {tab.label}
                </DailyNavLink>
              ))}
              <span
                aria-hidden
                className="mx-2 h-7 w-[2px] bg-[var(--daily-ink)]"
              />
              <Link
                href={SITE_LINKS.donate.href}
                className={cn(
                  PRESSABLE,
                  'inline-flex items-center gap-1.5 rounded-[4px] border-2 border-[var(--daily-ink)] bg-[#E9C46A] px-4 py-1.5 text-xs font-black uppercase tracking-[0.14em] text-[#1A1A1A] shadow-[3px_3px_0_0_var(--daily-ink)]',
                )}
              >
                <HeartIcon className="size-3.5" />
                {SITE_LINKS.donate.label}
              </Link>
            </nav>
          </>
        )}
      </div>
    </header>
  );
}

export default DailyHeader;
