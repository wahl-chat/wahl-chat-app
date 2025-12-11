import { cn, type UserDetails } from '@/lib/utils';
import type { NavbarItemDetails } from './navbar-item';
import NavbarItem from './navbar-item';
import { Separator } from '@/components/ui/separator';
import LoginButton from '@/components/auth/login-button';
import { Button } from '@/components/ui/button';
import UserAvatar from '@/components/auth/user-avatar';
import { SparklesIcon } from 'lucide-react';

type Props = {
  userDetails?: UserDetails;
  mobileClose?: () => void;
};

function MobileNavbarItems({ userDetails, mobileClose }: Props) {
  const tabs: NavbarItemDetails[] = [
    {
      label: 'Startseite',
      href: '/',
    },
    {
      label: 'Anleitung',
      href: '/how-to',
    },
    {
      label: 'Wahl Swiper',
      href: '/swiper',
      highlight: true,
      icon: <SparklesIcon className="size-3" />,
    },
    {
      label: 'Unterstütze uns',
      href: '/donate',
    },
    {
      label: 'Über uns',
      href: '/about-us',
    },
  ];

  return (
    <nav
      className={cn(
        'flex flex-col md:flex-row items-center justify-center gap-2',
      )}
    >
      {tabs.map((tab) => (
        <NavbarItem key={tab.href} details={tab} mobileClose={mobileClose} />
      ))}

      <Separator orientation="horizontal" className="my-4 w-1/2" />
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

export default MobileNavbarItems;
