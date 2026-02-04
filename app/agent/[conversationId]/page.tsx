'use client';

import AgentChatView from '@/components/agent/agent-chat-view';
import CompletionScreen from '@/components/agent/completion-screen';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import {
  type SourcesReadyPayload,
  getConversationMessages,
  getConversationStage,
  getConversationTopic,
} from '@/lib/agent/agent-api';
import {
  clearStoredConversation,
  saveConversationId,
} from '@/lib/agent/conversation-storage';
import type { Source } from '@/lib/stores/chat-store.types';
import { Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { use, useEffect, useState } from 'react';

interface PageProps {
  params: Promise<{ conversationId: string }>;
}

// Helper to flatten per-party sources into a single array with party_id on each source
const flattenSources = (sourcesPayload: SourcesReadyPayload[]): Source[] => {
  const flattened: Source[] = [];
  for (const partyGroup of sourcesPayload) {
    for (const source of partyGroup.sources) {
      flattened.push({
        ...source,
        party_id: partyGroup.party_id,
      });
    }
  }
  return flattened;
};

export default function ConversationPage({ params }: PageProps) {
  const { conversationId } = use(params);
  const router = useRouter();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const storeConversationId = useAgentStore((state) => state.conversationId);
  const step = useAgentStore((state) => state.step);
  const restoreConversation = useAgentStore(
    (state) => state.restoreConversation,
  );

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
          sources: msg.sources ? flattenSources(msg.sources) : undefined,
        }));

        // Restore the conversation in the store
        restoreConversation(
          conversationId,
          messages,
          topicRes.topic,
          stageRes.stage,
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
