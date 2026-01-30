'use client';

import { useEffect, useState } from 'react';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import AgentFlowController from './agent-flow-controller';
import ResumeConversationPrompt from './resume-conversation-prompt';
import { getStoredConversationId } from '@/lib/agent/conversation-storage';

export default function AgentEntryPoint() {
    const step = useAgentStore((state) => state.step);
    const [storedConversationId, setStoredConversationId] = useState<string | null>(null);
    const [hasCheckedStorage, setHasCheckedStorage] = useState(false);
    const [showResumePrompt, setShowResumePrompt] = useState(false);

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
