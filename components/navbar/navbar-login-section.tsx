'use client';

import LoginButton from '@/components/auth/login-button';
import UserAvatar from '@/components/auth/user-avatar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { isProlificStudy } from '@/lib/study/prolific-params';
import type { UserDetails } from '@/lib/utils';
import { useEffect, useState } from 'react';

type Props = {
  userDetails?: UserDetails;
  orientation?: 'horizontal' | 'vertical';
};

function NavbarLoginSection({ userDetails, orientation = 'vertical' }: Props) {
  const [isProlific, setIsProlific] = useState(false);

  useEffect(() => {
    setIsProlific(isProlificStudy());
  }, []);

  if (isProlific) {
    return null;
  }

  return (
    <>
      <Separator
        orientation={orientation}
        className={
          orientation === 'vertical' ? 'hidden h-8 md:block' : 'my-4 w-1/2'
        }
      />
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
  );
}

export default NavbarLoginSection;
