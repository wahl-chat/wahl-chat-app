import { setStudyParticipant } from '@/lib/firebase/firebase';
import { participationFor } from '@/lib/pledge-study/types';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { Timestamp } from 'firebase/firestore';

/**
 * A "Nein" is permanent per uid: persisted so the participant is never asked
 * again, on any device session with this browser profile. Dismissing the
 * dialog lands here too, so this is every refusal. Declined users get no
 * cohort and no telemetry — their experience is the study-off default (which,
 * in a study context, means no PledgeTracker).
 *
 * Context and party selection ARE recorded, for both answers, so non-response
 * can be modelled rather than just counted: refusal rates per election, and
 * per party the user came to chat with.
 *
 * `stage` and `reason` record WHERE and HOW the refusal happened, because all
 * four paths (a "Nein" on either screen, a dismissal of either screen) land
 * here and used to be indistinguishable in the data. Refusing the one-line ask
 * is a different act from reading the Einverständniserklärung and backing out,
 * and a dismissal is not an answer at all.
 */
export const declineStudyConsent: ChatStoreActionHandlerFor<
  'declineStudyConsent'
> = (_get, set) => async (userId, contextId, partyIds, decline) => {
  set({ studyConsent: 'declined' });
  try {
    await setStudyParticipant(userId, {
      consent_answer: 'declined',
      consent_at: Timestamp.now(),
      participation: participationFor('declined'),
      consent_stage: decline.stage,
      decline_reason: decline.reason,
      context_id: contextId,
      party_ids: partyIds,
    });
  } catch (error) {
    console.error('[Study] failed to persist declined consent:', error);
  }
};
