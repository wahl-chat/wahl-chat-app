import Logo from '@/components/chat/logo';
import { LocaleSwitcher } from '@/components/locale/locale-switcher';
import { Link } from '@/i18n/navigation';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED, getUserDetailsFromUser } from '@/lib/utils';
import { getTranslations } from 'next-intl/server';
import MobileNavbar from './navbar/mobile-navbar';
import NavBar from './navbar/navbar';

async function Header() {
  const user = !IS_EMBEDDED ? await getCurrentUser() : undefined;
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;
  const t = await getTranslations('header');

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background px-4 py-2 md:px-0">
      <div className="relative mx-auto flex max-w-xl items-center justify-between gap-2 md:flex-row">
        <Link href="/" aria-label={t('home')}>
          <Logo className="size-12 md:size-16" />
        </Link>

        <div className="flex items-center gap-2">
          {!IS_EMBEDDED && <LocaleSwitcher className="h-9" />}
          {!IS_EMBEDDED && <MobileNavbar userDetails={userDetails} />}
          <NavBar className="hidden md:flex" />
        </div>
      </div>
    </header>
  );
}

export default Header;
