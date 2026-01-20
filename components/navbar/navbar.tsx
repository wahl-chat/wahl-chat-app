import EmbedOpenWebsiteButton from '@/components/embed-open-website-button';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED, cn, getUserDetailsFromUser } from '@/lib/utils';
import { SparklesIcon } from 'lucide-react';
import type { NavbarItemDetails } from './navbar-item';
import NavbarLoginSection from './navbar-login-section';
import NavbarTabs from './navbar-tabs';

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
      {!IS_EMBEDDED ? <NavbarTabs tabs={tabs} /> : <EmbedOpenWebsiteButton />}

      <NavbarLoginSection userDetails={userDetails} orientation="vertical" />
    </nav>
  );
}
