import { setStudyParticipant } from '@/lib/firebase/firebase';
import { assignCohort } from '@/lib/pledge-study/study-config';
import { participationFor } from '@/lib/pledge-study/types';
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
> = (get, set) => async (userId, contextId, partyIds) => {
  // A forced variant wins over the hash, or accepting here would silently
  // re-randomise a tester who arrived on a ?sg= link.
  const override = get().studyOverride;
  const cohort = override?.cohort ?? assignCohort(userId);
  set({ studyConsent: 'accepted', studyCohort: cohort });
  try {
    await setStudyParticipant(userId, {
      consent_answer: 'accepted',
      consent_at: Timestamp.now(),
      participation: participationFor('accepted'),
      cohort,
      assignment_source: override ? 'override' : 'hash',
      context_id: contextId,
      party_ids: partyIds,
    });
  } catch (error) {
    console.error('[Study] failed to persist consent:', error);
  }
};
