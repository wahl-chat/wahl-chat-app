'use client';

import { useEffect, useState, use } from 'react';
import { useRouter } from 'next/navigation';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import AgentChatView from '@/components/agent/agent-chat-view';
import CompletionScreen from '@/components/agent/completion-screen';
import { Loader2 } from 'lucide-react';
import {
    getConversationMessages,
    getConversationTopic,
    getConversationStage,
} from '@/lib/agent/agent-api';
import {
    saveConversationId,
    clearStoredConversation,
} from '@/lib/agent/conversation-storage';

interface PageProps {
    params: Promise<{ conversationId: string }>;
}

export default function ConversationPage({ params }: PageProps) {
    const { conversationId } = use(params);
    const router = useRouter();

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const storeConversationId = useAgentStore((state) => state.conversationId);
    const step = useAgentStore((state) => state.step);
    const restoreConversation = useAgentStore((state) => state.restoreConversation);

    useEffect(() => {
        const loadConversation = async () => {
            // Skip if already loaded this conversation
            if (storeConversationId === conversationId) {
                setIsLoading(false);
                return;
            }

            setIsLoading(true);
            setError(null);

            try {
                // Fetch all conversation data in parallel
                const [messagesRes, topicRes, stageRes] = await Promise.all([
                    getConversationMessages(conversationId),
                    getConversationTopic(conversationId),
                    getConversationStage(conversationId),
                ]);

                // Map the messages to the correct format
                const messages = messagesRes.messages.map((msg) => ({
                    role: (msg.role === 'human' ? 'user' : 'assistant') as
                        | 'user'
                        | 'assistant',
                    content: msg.content,
                }));

                // Restore the conversation in the store
                restoreConversation(
                    conversationId,
                    messages,
                    topicRes.topic,
                    stageRes.stage
                );

                // Save to localStorage for future visits
                saveConversationId(conversationId);
            } catch (err) {
                console.error('Error loading conversation:', err);
                setError('Conversation not found');
                // Clear any stale localStorage data
                clearStoredConversation();
                // Redirect to consent screen
                router.replace('/agent');
            } finally {
                setIsLoading(false);
            }
        };

        loadConversation();
    }, [conversationId, storeConversationId, restoreConversation, router]);

    if (isLoading) {
        return (
            <div className="flex h-full flex-col items-center justify-center gap-3">
                <Loader2 className="size-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                    Unterhaltung wird geladen...
                </p>
            </div>
        );
    }

    if (error) {
        // This will briefly show before redirect
        return (
            <div className="flex h-full flex-col items-center justify-center gap-3">
                <p className="text-sm text-muted-foreground">Weiterleitung...</p>
            </div>
        );
    }

    // Show completion screen if step is completed
    if (step === 'completed') {
        return <CompletionScreen />;
    }

    return <AgentChatView />;
}
