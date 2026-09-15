'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { listenToStudyStatus } from '@/lib/firebase/firebase';
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

  // Kill switch: subscribe only where the study can apply at all.
  useEffect(() => {
    if (!inStudyContext) {
      return;
    }
    return listenToStudyStatus(({ enabled }) => setStudyEnabled(enabled));
  }, [inStudyContext, setStudyEnabled]);

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
