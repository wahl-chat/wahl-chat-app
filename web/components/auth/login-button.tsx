'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';
import { type UserDetails, getUserDetailsFromUser } from '@/lib/utils';
import { useState } from 'react';
import LoginForm, { type LoginPurpose } from './login-form';
import UserDialog from './user-dialog';

type Props = {
  userDialogAsChild?: boolean;
  noUserChildren?: React.ReactNode;
  userChildren?: React.ReactNode;
  userDetails?: UserDetails;
  purpose?: LoginPurpose;
};

function LoginButton({
  noUserChildren,
  userChildren,
  userDetails,
  userDialogAsChild,
  purpose,
}: Props) {
  const { user } = useAnonymousAuth();
  const [isOpen, setIsOpen] = useState(false);

  const handleSuccess = () => {
    setIsOpen(false);

    // hacky fix since the sidebar collides with the drawer's pointer events settings
    setTimeout(() => {
      if (document) {
        document.body.style.pointerEvents = 'auto';
      }
    }, 500);
  };

  const clientUserDetails = user ? getUserDetailsFromUser(user) : undefined;

  const hasUser = clientUserDetails
    ? !clientUserDetails.isAnonymous
    : userDetails
      ? !userDetails.isAnonymous
      : false;

  if (hasUser && !isOpen) {
    if (!userChildren) {
      return null;
    }

    return (
      <UserDialog
        details={userDetails ?? clientUserDetails}
        asChild={userDialogAsChild}
      >
        {userChildren}
      </UserDialog>
    );
  }

  return (
    <>
      <ResponsiveDialog open={isOpen} onOpenChange={setIsOpen}>
        <ResponsiveDialogTrigger asChild>
          {noUserChildren}
        </ResponsiveDialogTrigger>
        {/* Scrolls on short screens: the "Meine Woche" pitch with its sample
            email is taller than a phone. The inner box scrolls, so the
            drawer's handle stays put and a drag still closes it. */}
        <ResponsiveDialogContent className="flex max-h-[95dvh] flex-col">
          <div className="min-h-0 overflow-y-auto overscroll-contain">
            <LoginForm onSuccess={handleSuccess} purpose={purpose} />
          </div>
        </ResponsiveDialogContent>
      </ResponsiveDialog>
    </>
  );
}

export default LoginButton;
