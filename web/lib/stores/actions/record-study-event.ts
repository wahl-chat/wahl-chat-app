import { appendStudyParticipantEvent } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { Timestamp } from 'firebase/firestore';

/**
 * Consent-gated interaction log on study_participants/{uid}: a strict no-op
 * for non-participants (control AND experimental participants are logged —
 * the analysis needs both sides), and it never throws — telemetry must not
 * break chat. Counts/firsts are derived from the event log at analysis time.
 */
export const recordStudyEvent: ChatStoreActionHandlerFor<'recordStudyEvent'> =
  (get) => async (type, options) => {
    const { userId, studyConsent } = get();
    if (!userId || studyConsent !== 'accepted') {
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
