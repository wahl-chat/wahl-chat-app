import { appendStudyParticipantEvent } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { Timestamp } from 'firebase/firestore';

/**
 * Interaction log on study_participants/{uid}, written for everyone who has
 * ANSWERED the consent dialog — both arms and both answers, because both arms
 * now contain declined users and the analysis needs every side. A user who was
 * never asked (no answer, hence no row) is a strict no-op: logging them would
 * mint participant rows for people the dialog never reached and destroy the
 * consent denominator. Never throws — telemetry must not break chat.
 * Counts/firsts are derived from the event log at analysis time.
 */
export const recordStudyEvent: ChatStoreActionHandlerFor<'recordStudyEvent'> =
  (get) => async (type, options) => {
    const { userId, studyConsent } = get();
    if (!userId || !studyConsent) {
      return;
    }
    try {
      await appendStudyParticipantEvent(
        userId,
        {
          type,
          ...(options?.trigger ? { trigger: options.trigger } : {}),
          at: Timestamp.now(),
        },
        options?.merge,
      );
    } catch (error) {
      console.error('[Study] failed to record event:', error);
    }
  };
