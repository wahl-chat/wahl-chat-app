import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED, cn, getUserDetailsFromUser } from '@/lib/utils';
import { getTranslations } from 'next-intl/server';
import type { NavbarItemDetails } from './navbar-item';
import NavbarItem from './navbar-item';

type Props = {
  className?: string;
};

export default async function NavBar({ className }: Props) {
  const t = await getTranslations('nav');
  const tabs: NavbarItemDetails[] = [
    {
      label: t('home'),
      href: '/',
    },
    // {
    //   label: 'Wahl Swiper',
    //   href: '/swiper',
    //   highlight: true,
    //   icon: <SparklesIcon className="size-3" />,
    // },
    {
      label: t('howTo'),
      href: '/how-to',
    },
    {
      label: t('chat'),
      href: '/chat',
    },
  ];

  const user = !IS_EMBEDDED ? await getCurrentUser() : undefined;
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <nav
      className={cn(
        'flex flex-col md:flex-row items-center justify-center gap-2',
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
                {t('login')}
              </Button>
            }
            userChildren={<UserAvatar details={userDetails} />}
          />
        </>
      )}
    </nav>
  );
}
