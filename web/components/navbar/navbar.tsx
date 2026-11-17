import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { SITE_LINKS } from '@/lib/site-links';
import { IS_EMBEDDED, cn, getUserDetailsFromUser } from '@/lib/utils';
import {
  CircleHelpIcon,
  MessageCircleIcon,
  NewspaperIcon,
  VoteIcon,
} from 'lucide-react';
import type { NavbarItemDetails } from './navbar-item';
import NavbarItem from './navbar-item';

type Props = {
  className?: string;
};

export default async function NavBar({ className }: Props) {
  // The same links on every screen size: no menu to unfold. Spenden and
  // Über uns sit on the how-to page and in the footer.
  const tabs: NavbarItemDetails[] = [
    // The start page is the parliament feed, wahl.chat's News.
    { label: 'News', href: '/', icon: <NewspaperIcon /> },
    { ...SITE_LINKS.chat, icon: <MessageCircleIcon /> },
    { ...SITE_LINKS.elections, icon: <VoteIcon /> },
    { ...SITE_LINKS.howTo, icon: <CircleHelpIcon /> },
  ];

  const user = !IS_EMBEDDED ? await getCurrentUser() : undefined;
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <nav
      className={cn(
        'flex flex-row items-center justify-center gap-0.5 md:gap-2',
        className,
      )}
    >
      {!IS_EMBEDDED && (
        <>
          {tabs.map((tab) => (
            <NavbarItem key={tab.href} details={tab} />
          ))}
          <Separator orientation="vertical" className="hidden h-8 md:block" />
          <LoginButton
            userDetails={userDetails}
            noUserChildren={
              <Button variant="default" size="sm">
                Anmelden
              </Button>
            }
            userChildren={<UserAvatar details={userDetails} />}
          />
        </>
      )}
    </nav>
  );
}
