'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import LoginButton from '@/components/auth/login-button';
import { useStudyRunning } from '@/components/providers/study-status-provider';
import { Button } from '@/components/ui/button';
import type { UserDetails } from '@/lib/utils';
import { FilloutPopupEmbed } from '@fillout/react';
import { StarIcon, UserIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import '@fillout/react/style.css';

type Props = {
  resultId: string;
  userDetails?: UserDetails;
};

function WahlSwiperSurveyLoginCard({ resultId, userDetails }: Props) {
  const t = useTranslations('swiper.survey');
  const [open, setOpen] = useState(false);
  const [userClosedSurvey, setUserClosedSurvey] = useState(false);
  const { user } = useAnonymousAuth();
  const studyRunning = useStudyRunning();

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

  // While the PledgeTracker study runs, its questionnaire is the only survey
  // we put in front of anyone.
  if (studyRunning) {
    return null;
  }

  return (
    <section className="flex w-full flex-col gap-2 rounded-md border border-border bg-muted p-4">
      <div className="flex flex-col gap-1">
        <h1 className="font-bold">{t('title')}</h1>

        <p className="text-sm text-muted-foreground">
          {t('intro')}
          {!hasValidUser && ` ${t('signUpHint')}`}
        </p>
      </div>

      <div className="flex gap-2">
        <LoginButton
          userDetails={userDetails}
          noUserChildren={
            <Button size="sm">
              <UserIcon />
              {t('signIn')}
            </Button>
          }
        />

        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <StarIcon />
          {t('feedback')}
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
