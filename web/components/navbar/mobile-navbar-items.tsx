import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { SITE_LINKS } from '@/lib/site-links';
import { type UserDetails, cn } from '@/lib/utils';
import type { NavbarItemDetails } from './navbar-item';
import NavbarItem from './navbar-item';

type Props = {
  userDetails?: UserDetails;
  mobileClose?: () => void;
  onFeedback: () => void;
  /** Shown only to readers who consented to storing their opinions. */
  onDeleteOpinions?: () => void;
};

function MobileNavbarItems({
  userDetails,
  mobileClose,
  onFeedback,
  onDeleteOpinions,
}: Props) {
  const tabs: NavbarItemDetails[] = [
    // The start page is the parliament feed, wahl.chat's News.
    {
      label: 'News',
      href: '/',
    },
    {
      label: 'Anleitung',
      href: '/how-to',
    },
    SITE_LINKS.chat,
    // {
    //   label: 'Wahl Swiper',
    //   href: '/swiper',
    //   highlight: true,
    //   icon: <SparklesIcon className="size-3" />,
    // },
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
    <nav className={cn('flex flex-col items-center justify-center gap-2')}>
      {tabs.map((tab) => (
        <NavbarItem key={tab.href} details={tab} mobileClose={mobileClose} />
      ))}
      <button
        type="button"
        onClick={onFeedback}
        className="relative flex items-center gap-1 rounded-md p-2 text-sm text-primary/50 hover:text-primary/70"
      >
        Feedback
      </button>
      {onDeleteOpinions && (
        <button
          type="button"
          onClick={onDeleteOpinions}
          className="relative flex items-center gap-1 rounded-md p-2 text-sm text-primary/50 hover:text-primary/70"
        >
          Meine Bewertungen löschen
        </button>
      )}

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
      {/* The feed shows this menu on desktop too, where the toggle would
          otherwise align its dropdown to the start. */}
      <ThemeModeToggle align="center" />
    </nav>
  );
}

export default MobileNavbarItems;
