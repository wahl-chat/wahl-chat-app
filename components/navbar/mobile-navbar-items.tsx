import { type UserDetails, cn } from '@/lib/utils';
import { SparklesIcon } from 'lucide-react';
import type { NavbarItemDetails } from './navbar-item';
import NavbarLoginSection from './navbar-login-section';
import NavbarTabs from './navbar-tabs';

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
      <NavbarTabs tabs={tabs} mobileClose={mobileClose} />

      <NavbarLoginSection userDetails={userDetails} orientation="horizontal" />
    </nav>
  );
}

export default MobileNavbarItems;
