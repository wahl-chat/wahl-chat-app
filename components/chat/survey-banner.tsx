'use client';

import '@fillout/react/style.css';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import { SURVEY_BANNER_MIN_MESSAGE_COUNT } from '@/lib/stores/chat-store';
import { FilloutPopupEmbed } from '@fillout/react';
import { track } from '@vercel/analytics/react';
import { Timestamp } from 'firebase/firestore';
import { MessageCircleHeartIcon, XIcon } from 'lucide-react';
import { useEffect, useState } from 'react';

function SurveyBanner() {
  const sessionId = useChatStore((state) => state.chatSessionId);
  const [open, setOpen] = useState(false);
  const { user, updateUser, loading } = useAnonymousAuth();
  const showSurveyBanner = useChatStore(
    (state) =>
      state.messages.length >= SURVEY_BANNER_MIN_MESSAGE_COUNT &&
      !loading &&
      !user?.survey_status?.state,
  );
  const [optimisticShowSurveyBanner, setOptimisticShowSurveyBanner] =
    useState(showSurveyBanner);

  const handleCloseSurvey = () => {
    setOpen(false);
    setOptimisticShowSurveyBanner(false);

    if (!user?.uid) return;
    updateUser({
      survey_status: {
        state: 'opened',
        timestamp: Timestamp.now(),
      },
    });
  };

  const handleForceCloseSurvey = () => {
    setOptimisticShowSurveyBanner(false);

    track('survey_banner_force_closed');

    if (!user?.uid) return;
    updateUser({
      survey_status: {
        state: 'closed',
        timestamp: Timestamp.now(),
      },
    });
  };

  useEffect(() => {
    if (showSurveyBanner) return;

    if (
      user?.survey_status?.state === 'closed' &&
      user?.survey_status?.timestamp &&
      user?.survey_status?.timestamp instanceof Date
    ) {
      const now = new Date();
      const diff = now.getTime() - user.survey_status.timestamp.getTime();

      if (diff > 1000 * 60 * 60 * 24) {
        updateUser({
          survey_status: null,
        });
      }
    }
  }, [showSurveyBanner, user?.survey_status?.state]);

  useEffect(() => {
    if (showSurveyBanner) {
      setOptimisticShowSurveyBanner(true);
    }
  }, [showSurveyBanner]);

  if (!optimisticShowSurveyBanner) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg bg-muted p-4 group-data-[has-message-background]:mx-4 group-data-[has-message-background]:mb-4 group-data-[has-message-background]:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-800">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold">
          👆🏼 Hilf uns, wahl.chat zu verbessern!
        </h2>

        <Button
          size="icon"
          variant="ghost"
          className="size-6"
          onClick={handleForceCloseSurvey}
        >
          <XIcon />
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Wir würden uns sehr freuen, wenn du uns dein Feedback zu diesem Chat und
        unserer Plattform teilst.
      </p>
      <Button size="sm" variant="default" onClick={() => setOpen(true)}>
        <MessageCircleHeartIcon />
        Umfrage starten
      </Button>
      {open && (
        <FilloutPopupEmbed
          filloutId="cGozfJUor9us"
          onClose={handleCloseSurvey}
          parameters={{
            session_id: sessionId,
          }}
          inheritParameters
        />
      )}
    </div>
  );
}

export default SurveyBanner;
