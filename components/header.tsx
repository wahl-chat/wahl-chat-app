import Logo from '@/components/chat/logo';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED, getUserDetailsFromUser } from '@/lib/utils';
import Link from 'next/link';
import EmbedOpenWebsiteButton from './embed-open-website-button';
import MobileNavbar from './navbar/mobile-navbar';
import NavBar from './navbar/navbar';
import WahlSwiperTeaserTag from './wahl-swiper/wahl-swiper-teaser-tag';

async function Header() {
  const user = await getCurrentUser();
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background px-4 py-2 md:px-0">
      <div className="relative mx-auto flex max-w-xl items-center justify-between gap-2 md:flex-row">
        <Link href="/">
          <Logo className="size-12 md:size-16" />
        </Link>

        {IS_EMBEDDED ? (
          <div className="absolute inset-0 flex items-center justify-center md:hidden">
            <EmbedOpenWebsiteButton />
          </div>
        ) : (
          <WahlSwiperTeaserTag />
        )}

        <MobileNavbar userDetails={userDetails} />
        <NavBar className="hidden md:flex" />
      </div>
    </header>
  );
}

export default Header;
