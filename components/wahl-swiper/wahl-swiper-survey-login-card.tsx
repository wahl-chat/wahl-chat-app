'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import LoginButton from '@/components/auth/login-button';
import { Button } from '@/components/ui/button';
import type { UserDetails } from '@/lib/utils';
import { FilloutPopupEmbed } from '@fillout/react';
import { StarIcon, UserIcon } from 'lucide-react';
import { useState } from 'react';
import '@fillout/react/style.css';

type Props = {
  resultId: string;
  userDetails?: UserDetails;
};

function WahlSwiperSurveyLoginCard({ resultId, userDetails }: Props) {
  const [open, setOpen] = useState(false);
  const [userClosedSurvey, setUserClosedSurvey] = useState(false);
  const { user } = useAnonymousAuth();

  const handleCloseSurvey = () => {
    setOpen(false);
    setUserClosedSurvey(true);
  };

  const hasValidUser = user
    ? !user.isAnonymous
    : userDetails
      ? !userDetails.isAnonymous
      : false;

  if (userClosedSurvey && hasValidUser) {
    return null;
  }

  return (
    <section className="flex w-full flex-col gap-2 rounded-md border border-border bg-muted p-4">
      <div className="flex flex-col gap-1">
        <h1 className="font-bold">⭐️ Bitte gib uns dein Feedback</h1>

        <p className="text-sm text-muted-foreground">
          Wir würden uns sehr freuen, wenn du uns dein Feedback zu unserem Wahl
          Swiper mitteilst.
          {!hasValidUser &&
            ' Wenn du auch weiterhin nach der Wahl von uns benachrichtigt werden möchtest wenn deine Meinungen auch umgesetzt werden, kannst du dich hier anmelden.'}
        </p>
      </div>

      <div className="flex gap-2">
        <LoginButton
          userDetails={userDetails}
          noUserChildren={
            <Button size="sm">
              <UserIcon />
              Anmelden
            </Button>
          }
        />

        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <StarIcon />
          Feedback
        </Button>
      </div>
      {open && (
        <FilloutPopupEmbed
          filloutId="kyYP68KHyhus"
          onClose={handleCloseSurvey}
          parameters={{
            result_id: resultId,
          }}
        />
      )}
    </section>
  );
}

export default WahlSwiperSurveyLoginCard;
