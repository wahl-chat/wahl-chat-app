import { getStudyParticipant } from '@/lib/firebase/firebase';
import { readDevCohortOverride } from '@/lib/pledge-study/dev-cohort-override';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

/**
 * Consent is sticky per uid: seed the store from study_participants/{uid} so a
 * returning participant is never re-asked and keeps their cohort. The prompt
 * count is derived from the persisted event log so the questionnaire cap
 * survives reloads.
 *
 * On a read failure the store is marked hydrated-but-unanswered: the consent
 * dialog may show again, which is harmless — the cohort hash is deterministic,
 * so a re-consent writes the identical assignment.
 */
export const hydrateStudyParticipant: ChatStoreActionHandlerFor<
  'hydrateStudyParticipant'
> = (_get, set) => async (userId) => {
  try {
    const participant = await getStudyParticipant(userId);
    const promptCount =
      participant?.events?.filter((event) => event.type === 'prompt_shown')
        .length ?? 0;
    set({
      studyHydrated: true,
      studyConsent: participant?.consent_answer,
      // Dev-only override wins over the persisted assignment; a no-op in any
      // production build (see dev-cohort-override.ts).
      studyCohort: readDevCohortOverride() ?? participant?.group,
      studyPromptCount: promptCount,
      studyQuestionnaireClicked: Boolean(participant?.questionnaire_clicked_at),
    });
  } catch (error) {
    console.error('[Study] failed to hydrate participant:', error);
    set({ studyHydrated: true });
  }
};
