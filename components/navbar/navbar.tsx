import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import EmbedOpenWebsiteButton from '@/components/embed-open-website-button';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED, cn, getUserDetailsFromUser } from '@/lib/utils';
import { SparklesIcon } from 'lucide-react';
import type { NavbarItemDetails } from './navbar-item';
import NavbarItem from './navbar-item';

type Props = {
  className?: string;
};

export default async function NavBar({ className }: Props) {
  const tabs: NavbarItemDetails[] = [
    {
      label: 'Startseite',
      href: '/',
    },
    {
      label: 'Wahl Swiper',
      href: '/swiper',
      highlight: true,
      icon: <SparklesIcon className="size-3" />,
    },
    {
      label: 'Anleitung',
      href: '/how-to',
    },
  ];

  const user = await getCurrentUser();
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <nav
      className={cn(
        'flex flex-col md:flex-row items-center justify-center gap-2',
        className,
      )}
    >
      {!IS_EMBEDDED ? (
        <>
          {tabs.map((tab) => (
            <NavbarItem key={tab.href} details={tab} />
          ))}
        </>
      ) : (
        <EmbedOpenWebsiteButton />
      )}

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
    </nav>
  );
}
