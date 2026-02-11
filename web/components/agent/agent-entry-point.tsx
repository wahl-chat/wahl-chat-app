'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { getStoredConversationId } from '@/lib/agent/conversation-storage';
import { useEffect, useState } from 'react';
import AgentFlowController from './agent-flow-controller';
import ResumeConversationPrompt from './resume-conversation-prompt';
import { useSearchParams } from 'next/navigation';
import { captureProlificParams } from '@/lib/prolific-study/prolific-metadata';

export default function AgentEntryPoint() {
  const step = useAgentStore((state) => state.step);
  const setProlificMetadata = useAgentStore(
    (state) => state.setProlificMetadata,
  );
  const [storedConversationId, setStoredConversationId] = useState<
    string | null
  >(null);
  const [hasCheckedStorage, setHasCheckedStorage] = useState(false);
  const [showResumePrompt, setShowResumePrompt] = useState(false);

  const searchParams = useSearchParams();

  // Capture Prolific URL Params on mount
  useEffect(() => {
    const metadata = captureProlificParams(searchParams);
    if (metadata) {
      setProlificMetadata(metadata);
    }
  }, []);

  // Check localStorage on mount
  useEffect(() => {
    const savedId = getStoredConversationId();
    setStoredConversationId(savedId);
    setHasCheckedStorage(true);

    // Only show resume prompt if we have a saved conversation and user is at the start
    if (savedId && step === 'consent') {
      setShowResumePrompt(true);
    }
  }, [step]);

  // Don't render until we've checked localStorage
  if (!hasCheckedStorage) {
    return null;
  }

  // Show resume prompt if applicable
  if (showResumePrompt && storedConversationId) {
    return (
      <ResumeConversationPrompt
        conversationId={storedConversationId}
        onStartNew={() => setShowResumePrompt(false)}
      />
    );
  }

  // Normal flow
  return <AgentFlowController />;
}
