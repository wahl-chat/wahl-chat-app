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
  absoluteFallbackRemainingMs,
  isPromptEligible,
} from '@/lib/pledge-study/prompt-triggers';
import {
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
 * Shows the questionnaire prompt.
 *
 * Both cohorts use identical rules, and nothing here reads PledgeTracker
 * state. That is the whole point: every earlier modal-driven trigger could
 * only fire for the manipulation arm, so the two arms were prompted on
 * different paths — a difference inside the instrument measuring the outcome.
 *
 * Two triggers, whichever comes first:
 *
 * 1. second_answer: the SECOND answer of the session finishes. The intended
 *    path — the user has read one answer and asked again, so the
 *    questionnaire reaches someone who has something to say about the
 *    product rather than someone who has merely arrived.
 * 2. absolute_timer: ABSOLUTE_FALLBACK_MS after the FIRST answer completes,
 *    and only while nothing has prompted yet. It catches the user who never
 *    sends a second message, so being asked at all does not depend on depth
 *    of engagement.
 *
 * Each trigger fires at most once per mount. MAX_PROMPTS is the hard cap and
 * is derived from the stored event log, so it survives a reload.
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
  const secondAnswerCompletedAt = useChatStore(
    (state) => state.secondAnswerCompletedAt,
  );
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
  // One shot per trigger: `eligible` turns true again after a dismissal, and
  // a still-satisfied condition would otherwise re-prompt on the next render.
  const secondAnswerFiredRef = useRef(false);
  const absoluteFiredRef = useRef(false);

  // Always resolves: the default form id is committed, and the env var only
  // overrides it. Turning the questionnaire off is the kill switch's job.
  const formId = questionnaireFormId();

  const eligible = isPromptEligible({
    consent: studyConsent,
    questionnaireClicked: Boolean(studyQuestionnaireClicked),
    promptCount: studyPromptCount,
    promptShowing: activePrompt !== null,
  });

  const showPrompt = useCallback(
    (trigger: QuestionnaireTrigger) => {
      setActivePrompt({ trigger });
      incrementStudyPromptCount();
      void recordStudyEvent('prompt_shown', { trigger });
    },
    [incrementStudyPromptCount, recordStudyEvent],
  );

  // second_answer — the primary trigger, fired the moment the second answer
  // of the session lands. No delay: the user has just finished a round trip,
  // which is the point at which they have an opinion to give.
  useEffect(() => {
    if (!eligible || secondAnswerFiredRef.current) {
      return;
    }
    if (secondAnswerCompletedAt === undefined) {
      return;
    }
    secondAnswerFiredRef.current = true;
    showPrompt('second_answer');
  }, [eligible, secondAnswerCompletedAt, showPrompt]);

  // absolute_timer — the safeguard, counted from the first completed answer.
  // The studyPromptCount check keeps it a fallback: once anything has asked,
  // this must not tap the same user again a few seconds later.
  useEffect(() => {
    if (!eligible || absoluteFiredRef.current || studyPromptCount > 0) {
      return;
    }
    if (firstAnswerCompletedAt === undefined) {
      return;
    }
    const remaining = absoluteFallbackRemainingMs(
      firstAnswerCompletedAt,
      Date.now(),
    );
    const timer = window.setTimeout(() => {
      absoluteFiredRef.current = true;
      showPrompt('absolute_timer');
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [eligible, studyPromptCount, firstAnswerCompletedAt, showPrompt]);

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
              ein paar kurze Fragen zu deinem heutigen Besuch stellen, es dauert
              höchstens 2 Minuten.
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
