import {
  getStudyParticipant,
  setStudyParticipant,
} from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { Timestamp } from 'firebase/firestore';

/**
 * Consent is sticky per uid: seed the store from study_participants/{uid} so a
 * returning participant is never re-asked and keeps their cohort. The prompt
 * count is derived from the persisted event log so the questionnaire cap
 * survives reloads.
 *
 * A ?sg= override beats the persisted record, in both branches — on a read
 * failure the override must still apply, or a tester who forced a variant gets
 * the real consent dialog instead.
 */
export const hydrateStudyParticipant: ChatStoreActionHandlerFor<
  'hydrateStudyParticipant'
> = (get, set) => async (userId) => {
  const override = get().studyOverride;

  try {
    const participant = await getStudyParticipant(userId);
    const events = participant?.events ?? [];
    const promptCount = events.filter(
      (event) => event.type === 'prompt_shown',
    ).length;
    // Answers already completed by this participant, so a second question
    // asked after a reload or in a new tab still counts as the second one.
    // Each of these events is logged once per participant, never per chat.
    const answersCompleted =
      (events.some((event) => event.type === 'first_answer_completed')
        ? 1
        : 0) +
      (events.some((event) => event.type === 'second_answer_completed')
        ? 1
        : 0);
    set({
      studyHydrated: true,
      studyConsent: override?.consent ?? participant?.consent_answer,
      studyCohort: override?.cohort ?? participant?.cohort,
      studyPromptCount: promptCount,
      studyAnswersCompleted: answersCompleted,
      studyQuestionnaireClicked: Boolean(participant?.questionnaire_clicked_at),
    });
  } catch (error) {
    console.error('[Study] failed to hydrate participant:', error);
    set({
      studyHydrated: true,
      studyConsent: override?.consent,
      studyCohort: override?.cohort,
    });
  }

  if (override) {
    // Marker fields ONLY. Never consent_answer or cohort: if this uid happens
    // to be a genuine participant, their real assignment must survive intact
    // and merely gain the exclusion flag.
    void setStudyParticipant(userId, {
      assignment_source: 'override',
      override_variant: override.variant,
      override_at: Timestamp.now(),
    }).catch((error) => {
      console.error('[Study] failed to flag forced assignment:', error);
    });
  }
};
