'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { useStudyRunning } from '@/components/providers/study-status-provider';
import { isStudyContext } from '@/lib/pledge-study/study-config';
import { isProlificStudy } from '@/lib/prolific-study/prolific-metadata';
import { useEffect, useState } from 'react';
import ChatStudyConsent from './chat-study-consent';
import ChatStudyQuestionnairePrompt from './chat-study-questionnaire-prompt';

/**
 * Self-gating mount point for the PledgeTracker study (Vlachos group):
 * renders nothing outside the two study contexts, while the Firestore kill
 * switch is off, for Prolific participants, or before the uid and the
 * participant record are known. Everything study-related hangs off this
 * wrapper, so removing the study later is one mount-line plus this folder.
 */
function ChatStudyWrapper() {
  const { user } = useAnonymousAuth();
  const contextId = useChatStore((state) => state.contextId);
  const studyEnabled = useChatStore((state) => state.studyEnabled);
  const setStudyEnabled = useChatStore((state) => state.setStudyEnabled);
  const studyHydrated = useChatStore((state) => state.studyHydrated);
  const hydrateStudyParticipant = useChatStore(
    (state) => state.hydrateStudyParticipant,
  );

  // Check after mount to avoid hydration mismatch (prolific-wrapper pattern).
  const [isProlific, setIsProlific] = useState<boolean | null>(null);
  useEffect(() => {
    setIsProlific(isProlificStudy());
  }, []);

  const inStudyContext = isStudyContext(contextId);

  // The kill switch is subscribed once, app-wide, by StudyStatusProvider.
  // Mirror it into the store in EVERY context, not just the study ones: the
  // switch gates the feature everywhere now, so a non-study election needs the
  // value too — gate.ts reads an unknown switch as off, so without this its
  // pledge cards would stay hidden for good. Still only once it is actually
  // known: leaving studyEnabled undefined until then is what stops a
  // control-group user seeing a flash of PledgeTracker (see gate.ts).
  const studyRunning = useStudyRunning();
  useEffect(() => {
    if (studyRunning === undefined) {
      return;
    }
    setStudyEnabled(studyRunning);
  }, [studyRunning, setStudyEnabled]);

  // Load the participant record once per uid (consent stickiness).
  useEffect(() => {
    if (!inStudyContext || !studyEnabled || !user?.uid || studyHydrated) {
      return;
    }
    void hydrateStudyParticipant(user.uid);
  }, [
    inStudyContext,
    studyEnabled,
    user?.uid,
    studyHydrated,
    hydrateStudyParticipant,
  ]);

  if (!inStudyContext || isProlific !== false || !studyEnabled) {
    return null;
  }
  if (!user?.uid || !studyHydrated || !contextId) {
    return null;
  }

  return (
    <>
      <ChatStudyConsent userId={user.uid} contextId={contextId} />
      <ChatStudyQuestionnairePrompt userId={user.uid} />
    </>
  );
}

export default ChatStudyWrapper;
