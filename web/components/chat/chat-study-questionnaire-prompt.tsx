'use client';

import '@fillout/react/style.css';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import {
  MAX_PROMPTS,
  MODAL_LONGSTOP_MS,
  QUESTIONNAIRE_DELAY_MS,
  type QuestionnaireTrigger,
  questionnaireFormId,
} from '@/lib/pledge-study/study-config';
import { FilloutPopupEmbed } from '@fillout/react';
import { Timestamp } from 'firebase/firestore';
import { useCallback, useEffect, useRef, useState } from 'react';

type Props = {
  userId: string;
};

/**
 * Questionnaire prompt engine — the ratified trigger design, identical for
 * BOTH cohorts (control symmetry; "pledge card seen" is deliberately not an
 * arming condition):
 *
 * - timer:       QUESTIONNAIRE_DELAY_MS after the FIRST answer completes,
 *                fired only while idle (no streaming, no open pledge modal —
 *                the effect re-arms whenever idleness returns). First prompt
 *                only.
 * - modal_close: closing the pledge popup prompts immediately — measurement
 *                right after the treatment episode ends, never inside it.
 *                Also the single retry path after a dismissed prompt.
 * - longstop:    a pledge modal open for MODAL_LONGSTOP_MS prompts anyway
 *                (catches abandoned tabs mid-modal).
 *
 * Hard cap MAX_PROMPTS across reloads (count is derived from the persisted
 * event log on hydrate). Timing asymmetry between cohorts can only arise
 * from the participant's own use of the feature — part of the treatment —
 * never from group-dependent scheduling rules.
 */
function ChatStudyQuestionnairePrompt({ userId }: Props) {
  const studyConsent = useChatStore((state) => state.studyConsent);
  // The Firestore chat_sessions doc id (promoted from safeSessionId on the
  // first send), so a response joins to the chat and, through
  // page_visits.chat_session_ids, to that visit's dwell time.
  const chatSessionId = useChatStore((state) => state.chatSessionId);
  const firstAnswerCompletedAt = useChatStore(
    (state) => state.firstAnswerCompletedAt,
  );
  const pledgeModalOpen = useChatStore((state) => state.pledgeModalOpen);
  const streaming = useChatStore((state) => state.loading.newMessage);
  const studyPromptCount = useChatStore((state) => state.studyPromptCount);
  const studyQuestionnaireClicked = useChatStore(
    (state) => state.studyQuestionnaireClicked,
  );
  const incrementStudyPromptCount = useChatStore(
    (state) => state.incrementStudyPromptCount,
  );
  const setStudyQuestionnaireClicked = useChatStore(
    (state) => state.setStudyQuestionnaireClicked,
  );
  const recordStudyEvent = useChatStore((state) => state.recordStudyEvent);

  const [activePrompt, setActivePrompt] = useState<{
    trigger: QuestionnaireTrigger;
  } | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const prevModalOpenRef = useRef(false);

  // Always resolves: the default form id is committed, and the env var only
  // overrides it. Turning the questionnaire off is the kill switch's job.
  const formId = questionnaireFormId();

  const eligible =
    studyConsent === 'accepted' &&
    !studyQuestionnaireClicked &&
    studyPromptCount < MAX_PROMPTS &&
    activePrompt === null;

  const showPrompt = useCallback(
    (trigger: QuestionnaireTrigger) => {
      setActivePrompt({ trigger });
      incrementStudyPromptCount();
      void recordStudyEvent('prompt_shown', { trigger });
    },
    [incrementStudyPromptCount, recordStudyEvent],
  );

  // timer — first prompt only; re-arms whenever idleness returns, so the
  // remaining delay naturally defers past streaming and open modals.
  useEffect(() => {
    if (!eligible || studyPromptCount > 0) {
      return;
    }
    if (firstAnswerCompletedAt === undefined || pledgeModalOpen || streaming) {
      return;
    }
    const remaining = Math.max(
      0,
      QUESTIONNAIRE_DELAY_MS - (Date.now() - firstAnswerCompletedAt),
    );
    const timer = window.setTimeout(() => showPrompt('timer'), remaining);
    return () => window.clearTimeout(timer);
  }, [
    eligible,
    studyPromptCount,
    firstAnswerCompletedAt,
    pledgeModalOpen,
    streaming,
    showPrompt,
  ]);

  // modal_close — prompt on the open→closed transition.
  useEffect(() => {
    const wasOpen = prevModalOpenRef.current;
    prevModalOpenRef.current = pledgeModalOpen;
    if (wasOpen && !pledgeModalOpen && eligible) {
      showPrompt('modal_close');
    }
  }, [pledgeModalOpen, eligible, showPrompt]);

  // longstop — a modal held open past the cap prompts anyway.
  useEffect(() => {
    if (!eligible || !pledgeModalOpen) {
      return;
    }
    const timer = window.setTimeout(
      () => showPrompt('longstop'),
      MODAL_LONGSTOP_MS,
    );
    return () => window.clearTimeout(timer);
  }, [eligible, pledgeModalOpen, showPrompt]);

  const dismiss = () => {
    if (!activePrompt) {
      return;
    }
    void recordStudyEvent('prompt_dismissed', {
      trigger: activePrompt.trigger,
    });
    setActivePrompt(null);
  };

  const openQuestionnaire = () => {
    if (!activePrompt) {
      return;
    }
    setFormOpen(true);
    setStudyQuestionnaireClicked(true);
    void recordStudyEvent('questionnaire_clicked', {
      trigger: activePrompt.trigger,
      merge: { questionnaire_clicked_at: Timestamp.now() },
    });
    setActivePrompt(null);
  };

  return (
    <>
      <ResponsiveDialog
        open={activePrompt !== null}
        onOpenChange={(nextOpen) => !nextOpen && dismiss()}
      >
        <ResponsiveDialogContent>
          <ResponsiveDialogHeader>
            <ResponsiveDialogTitle>
              Deine Rückmeldung zählt
            </ResponsiveDialogTitle>
            <ResponsiveDialogDescription>
              Kurzer Fragebogen zur Studie
            </ResponsiveDialogDescription>
          </ResponsiveDialogHeader>
          <div className="px-4 text-sm md:px-0">
            <p>
              Danke, dass du bei unserer Studie mitmachst! Wir würden dir gern
              ein paar kurze Fragen zu deinem heutigen Besuch stellen — es
              dauert höchstens 2 Minuten.
            </p>
          </div>
          <ResponsiveDialogFooter>
            <div className="flex w-full flex-col gap-2 sm:flex-row">
              <Button variant="outline" className="w-full" onClick={dismiss}>
                Später
              </Button>
              <Button className="w-full" onClick={openQuestionnaire}>
                Zum Fragebogen
              </Button>
            </div>
          </ResponsiveDialogFooter>
        </ResponsiveDialogContent>
      </ResponsiveDialog>
      {formOpen && (
        <FilloutPopupEmbed
          filloutId={formId}
          parameters={{
            user_id: userId,
            chat_session_id: chatSessionId,
          }}
          onClose={() => setFormOpen(false)}
          inheritParameters
        />
      )}
    </>
  );
}

export default ChatStudyQuestionnairePrompt;
