'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import { FilloutPopupEmbed } from '@fillout/react';
import { UserIcon, XIcon } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import LoginForm from './login-form';
import '@fillout/react/style.css';
import Logo from '@/components/chat/logo';
import { firestoreTimestampToDate } from '@/lib/utils';
import { Timestamp } from 'firebase/firestore';
import { usePathname } from 'next/navigation';

const LOGIN_REMINDER_TOAST_ID = 'login-reminder-toast';

function LoginReminderToast() {
  const [isOpen, setIsOpen] = useState(false);
  const [surveyOpen, setSurveyOpen] = useState(false);
  const { user, updateUser } = useAnonymousAuth();
  const shownThisRender = useRef(false);
  const pathname = usePathname();

  useEffect(() => {
    if (
      !user?.isAnonymous ||
      shownThisRender.current ||
      pathname === '/' ||
      user.keep_up_to_date_email
    ) {
      return;
    }

    const clickedAway = firestoreTimestampToDate(
      user.clicked_away_login_reminder,
    );

    if (clickedAway) {
      const now = Date.now();
      const timeSinceClickedAway = now - clickedAway.getTime();

      // if last time clicked away is < 24 hours return
      if (timeSinceClickedAway < 24 * 60 * 60 * 1000) {
        return;
      }
    }

    // Calculate when to show the login reminder toast:
    // - If user account is older than 5 minutes, show after 2 second
    // - If user account is newer than 5 minutes, show after 2 minute
    const creationTime = user.metadata.creationTime
      ? new Date(user.metadata.creationTime).getTime()
      : Date.now();
    const now = Date.now();
    const timeSinceCreation = now - creationTime;
    const timeout = timeSinceCreation > 5 * 60 * 1000 ? 2000 : 60 * 1000;

    const handleClickedAway = () => {
      updateUser({ clicked_away_login_reminder: Timestamp.now() });
    };

    const handleLoginClick = () => {
      toast.dismiss(LOGIN_REMINDER_TOAST_ID);
      setIsOpen(true);
    };

    const handleFeedbackClick = () => {
      toast.dismiss(LOGIN_REMINDER_TOAST_ID);
      setSurveyOpen(true);
    };

    const handleClose = () => {
      toast.dismiss(LOGIN_REMINDER_TOAST_ID);
      handleClickedAway();
    };

    const timer = setTimeout(() => {
      if (shownThisRender.current) return;
      shownThisRender.current = true;

      toast(
        <div className="relative flex flex-col gap-2">
          <div className="absolute right-0 top-0">
            <Button
              variant="ghost"
              size="icon"
              className="-mr-2 -mt-2 size-6"
              onClick={handleClose}
            >
              <XIcon className="size-4" />
            </Button>
          </div>

          <div className="flex items-center gap-4">
            <Logo variant="small" className="size-6" />
            <div className="flex flex-col">
              <h1 className="text-base font-bold">Der Koalitionsvertrag!</h1>
              <p className="text-sm text-muted-foreground">
                Bald auf <span className="font-bold">wahl.chat</span>
              </p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            Melde dich an, um nach der Wahl zu erfahren, wie der
            Koalitionsvertrag umgesetzt wird und welche deiner Wünsche ins
            Programm aufgenommen wurden.
          </p>

          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" onClick={handleLoginClick}>
              Anmelden
            </Button>
            <Button variant="outline" size="sm" onClick={handleFeedbackClick}>
              Feedback
            </Button>
          </div>
        </div>,
        {
          duration: 10000,
          icon: <UserIcon className="size-4" />,
          position: 'bottom-right',
          id: LOGIN_REMINDER_TOAST_ID,
          onDismiss: handleClickedAway,
        },
      );
    }, timeout);

    return () => clearTimeout(timer);
  }, [
    user?.isAnonymous,
    user?.metadata.creationTime,
    updateUser,
    user?.clicked_away_login_reminder,
    pathname,
  ]);

  return (
    <>
      <ResponsiveDialog open={isOpen} onOpenChange={setIsOpen}>
        <ResponsiveDialogContent>
          <LoginForm onSuccess={() => setIsOpen(false)} />
        </ResponsiveDialogContent>
      </ResponsiveDialog>
      {surveyOpen && (
        <FilloutPopupEmbed
          filloutId="cGozfJUor9us"
          onClose={() => setSurveyOpen(false)}
          inheritParameters
        />
      )}
    </>
  );
}

export default LoginReminderToast;
