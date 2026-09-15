import { setStudyParticipant } from '@/lib/firebase/firebase';
import { assignCohort } from '@/lib/pledge-study/study-config';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { Timestamp } from 'firebase/firestore';

/**
 * Consent accepted: assign the cohort (deterministic hash of the uid) and
 * persist the participant record. The store is set FIRST so the UI (consent
 * dialog, PledgeTracker gate) reacts instantly; the Firestore doc is the
 * cross-session memory and the analysis source of truth.
 */
export const acceptStudyConsent: ChatStoreActionHandlerFor<
  'acceptStudyConsent'
> = (_get, set) => async (userId, contextId, partyIds) => {
  const group = assignCohort(userId);
  set({ studyConsent: 'accepted', studyCohort: group });
  try {
    await setStudyParticipant(userId, {
      consent_answer: 'accepted',
      consent_at: Timestamp.now(),
      group,
      context_id: contextId,
      party_ids: partyIds,
    });
  } catch (error) {
    console.error('[Study] failed to persist consent:', error);
  }
};
