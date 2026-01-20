'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { getStoredConversationId } from '@/lib/agent/conversation-storage';
import { captureProlificParams } from '@/lib/study/prolific-params';
import { useEffect, useState } from 'react';
import AgentFlowController from './agent-flow-controller';
import ResumeConversationPrompt from './resume-conversation-prompt';

interface AgentEntryPointProps {
  searchParams?: { [key: string]: string | string[] | undefined };
}

export default function AgentEntryPoint({
  searchParams,
}: AgentEntryPointProps) {
  const step = useAgentStore((state) => state.step);
  const setProlificMetadata = useAgentStore(
    (state) => state.setProlificMetadata,
  );
  const [storedConversationId, setStoredConversationId] = useState<
    string | null
  >(null);
  const [hasCheckedStorage, setHasCheckedStorage] = useState(false);
  const [showResumePrompt, setShowResumePrompt] = useState(false);

  // Capture Prolific params on mount
  useEffect(() => {
    if (searchParams) {
      const urlSearchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(searchParams)) {
        if (typeof value === 'string') {
          urlSearchParams.set(key, value);
        }
      }
      const metadata = captureProlificParams(urlSearchParams);
      if (metadata) {
        setProlificMetadata(metadata);
      }
    }
  }, [searchParams, setProlificMetadata]);

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
