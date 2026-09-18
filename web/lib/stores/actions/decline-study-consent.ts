import { setStudyParticipant } from '@/lib/firebase/firebase';
import { assignCohort } from '@/lib/pledge-study/study-config';
import { participationFor } from '@/lib/pledge-study/types';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { Timestamp } from 'firebase/firestore';

/**
 * A "Nein" is permanent per uid: persisted so the participant is never asked
 * again, on any device session with this browser profile. Dismissing the
 * dialog lands here too, so this is every refusal.
 *
 * A decline still ASSIGNS AN ARM. Consent governs the research instruments —
 * the questionnaire and nothing else asks these users anything — while the arm
 * governs which version of the product they get, and both arms are ordinary
 * product experiences. Assigning here is what makes the comparison wide enough
 * to mean anything: with consent alone, a single-digit number of people ever
 * reached the manipulation. The cohort is the same deterministic hash(uid) the
 * accept path uses, so a uid's arm never depends on which answer they gave.
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
> = (get, set) => async (userId, contextId, partyIds, decline) => {
  // A forced variant wins over the hash, INCLUDING its absence: the 'declined'
  // override (?sg=x) carries no arm on purpose, and hashing one in would turn
  // the one link that demonstrates the arm-less experience into a coin flip.
  const override = get().studyOverride;
  const cohort = override ? override.cohort : assignCohort(userId);
  set({ studyConsent: 'declined', studyCohort: cohort });
  try {
    await setStudyParticipant(userId, {
      consent_answer: 'declined',
      consent_at: Timestamp.now(),
      participation: participationFor('declined'),
      consent_stage: decline.stage,
      decline_reason: decline.reason,
      // Omitted rather than undefined: Firestore rejects undefined values.
      ...(cohort ? { cohort } : {}),
      assignment_source: override ? 'override' : 'hash',
      context_id: contextId,
      party_ids: partyIds,
    });
  } catch (error) {
    console.error('[Study] failed to persist declined consent:', error);
  }
};
