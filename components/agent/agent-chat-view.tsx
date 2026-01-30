'use client';

import AiDisclaimer from '@/components/legal/ai-disclaimer';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import {
  type SourcesReadyPayload,
  createConversation,
  getConversationStage,
  streamChatEvents,
} from '@/lib/agent/agent-api';
import { saveConversationId } from '@/lib/agent/conversation-storage';
import type { Source } from '@/lib/stores/chat-store.types';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { memo, useCallback, useEffect, useRef, useState } from 'react';
import AgentChatInput from './agent-chat-input';
import AgentChatMessage from './agent-chat-message';

// Sub-component: Messages area - only rerenders when messages or isStreaming changes
const AgentChatMessages = memo(
  ({
    scrollRef,
    isLoading,
  }: {
    scrollRef: React.RefObject<HTMLDivElement | null>;
    isLoading: boolean;
  }) => {
    const messages = useAgentStore((state) => state.messages);
    const isStreaming = useAgentStore((state) => state.isStreaming);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }, [messages, scrollRef]);

    return (
      <div ref={scrollRef} className="flex-1 overflow-y-auto scroll-smooth p-4">
        {isLoading ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Der Assistent formuliert die erste Nachricht...
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <AgentChatMessage
                key={message.id}
                message={message}
                isStreaming={
                  isStreaming &&
                  index === messages.length - 1 &&
                  message.role === 'assistant'
                }
              />
            ))}
          </div>
        )}
      </div>
    );
  },
);

AgentChatMessages.displayName = 'AgentChatMessages';

// Sub-component: Streaming indicator - only rerenders when isStreaming or progressMessage changes
const AgentStreamingIndicator = memo(
  ({
    progressMessage,
  }: {
    progressMessage: string | null;
  }) => {
    const isStreaming = useAgentStore((state) => state.isStreaming);

    return (
      <div className="h-8 shrink-0 px-4">
        {isStreaming && (
          <p className="text-center text-sm text-muted-foreground">
            {progressMessage ?? 'Der Wahl Agent denkt nach'}
            <span className="ml-0.5 inline-flex gap-0.5 align-baseline">
              <span
                className="inline-block size-1 animate-typing-dot rounded-full bg-muted-foreground"
                style={{ animationDelay: '0ms' }}
              />
              <span
                className="inline-block size-1 animate-typing-dot rounded-full bg-muted-foreground"
                style={{ animationDelay: '200ms' }}
              />
              <span
                className="inline-block size-1 animate-typing-dot rounded-full bg-muted-foreground"
                style={{ animationDelay: '400ms' }}
              />
            </span>
          </p>
        )}
      </div>
    );
  },
);

AgentStreamingIndicator.displayName = 'AgentStreamingIndicator';

// Sub-component: Footer with input or completion button - only rerenders when conversationStage changes
const AgentChatFooter = memo(
  ({
    onSubmit,
    onComplete,
  }: {
    onSubmit: (message: string) => Promise<void>;
    onComplete: () => void;
  }) => {
    const conversationStage = useAgentStore((state) => state.conversationStage);
    const isConversationEnded = conversationStage === 'end';

    return (
      <div className="shrink-0 px-3 pb-3 md:px-4 md:pb-4">
        {isConversationEnded ? (
          <Button onClick={onComplete} className="w-full gap-2" size="lg">
            <CheckCircle2 className="size-4" />
            Gespräch abschließen
          </Button>
        ) : (
          <AgentChatInput onSubmit={onSubmit} />
        )}
        <AiDisclaimer />
      </div>
    );
  },
);

AgentChatFooter.displayName = 'AgentChatFooter';

export default function AgentChatView() {
  const router = useRouter();

  const topic = useAgentStore((state) => state.topic);
  const userData = useAgentStore((state) => state.userData);
  const conversationId = useAgentStore((state) => state.conversationId);
  const isStreaming = useAgentStore((state) => state.isStreaming);
  const initialMessageReceived = useAgentStore(
    (state) => state.initialMessageReceived,
  );

  const setConversationId = useAgentStore((state) => state.setConversationId);
  const setConversationStage = useAgentStore(
    (state) => state.setConversationStage,
  );
  const setStep = useAgentStore((state) => state.setStep);
  const addMessage = useAgentStore((state) => state.addMessage);
  const setIsStreaming = useAgentStore((state) => state.setIsStreaming);
  const setInitialMessageReceived = useAgentStore(
    (state) => state.setInitialMessageReceived,
  );
  const updateLastAssistantMessage = useAgentStore(
    (state) => state.updateLastAssistantMessage,
  );
  const updateLastAssistantSources = useAgentStore(
    (state) => state.updateLastAssistantSources,
  );

  const [progressMessage, setProgressMessage] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const isInitializingRef = useRef(false);

  // Fetch and update conversation stage
  const fetchConversationStage = useCallback(
    async (convId: string) => {
      try {
        const response = await getConversationStage(convId);
        setConversationStage(response.stage);
      } catch (error) {
        console.error('Error fetching conversation stage:', error);
      }
    },
    [setConversationStage],
  );

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

  // Stream assistant response
  const streamAssistantResponse = useCallback(
    async (convId: string, userMessage: string) => {
      setIsStreaming(true);
      setProgressMessage(null);

      try {
        let currentContent = '';
        let pendingSources: Source[] = [];

        for await (const event of streamChatEvents(convId, userMessage)) {
          if (event.type === 'progress_update' && event.content) {
            setProgressMessage(event.content);
          } else if (event.type === 'sources_ready' && event.sources) {
            // Store sources to attach when message completes
            pendingSources = flattenSources(event.sources);
          } else if (event.type === 'message_start') {
            setProgressMessage(null);
            addMessage({ role: 'assistant', content: '' });
            currentContent = '';
          } else if (event.type === 'message_chunk' && event.content) {
            currentContent += event.content;
            updateLastAssistantMessage(currentContent);
          } else if (event.type === 'message_end') {
            // Attach sources if we received any
            if (pendingSources.length > 0) {
              updateLastAssistantSources(pendingSources);
              pendingSources = [];
            }
          } else if (event.type === 'end') {
            break;
          }
        }

        // Fetch updated conversation stage after message completes
        await fetchConversationStage(convId);
      } catch (error) {
        console.error('Error streaming response:', error);
        addMessage({
          role: 'assistant',
          content:
            'Es tut mir leid, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
        });
      } finally {
        setIsStreaming(false);
        setProgressMessage(null);
      }
    },
    [
      addMessage,
      setIsStreaming,
      updateLastAssistantMessage,
      updateLastAssistantSources,
      fetchConversationStage,
    ],
  );

  // Initialize conversation and get first message
  useEffect(() => {
    const initializeConversation = async () => {
      if (
        !topic ||
        !userData ||
        conversationId ||
        initialMessageReceived ||
        isInitializingRef.current
      ) {
        return;
      }

      isInitializingRef.current = true;

      try {
        // Create conversation
        const response = await createConversation(topic, userData);
        setConversationId(response.conversation_id);

        // Save to localStorage and update URL
        saveConversationId(response.conversation_id);
        router.replace(`/agent/${response.conversation_id}`);

        // Get initial message from assistant (empty user message triggers it)
        await streamAssistantResponse(response.conversation_id, '');
        setInitialMessageReceived(true);
      } catch (error) {
        console.error('Error initializing conversation:', error);
        addMessage({
          role: 'assistant',
          content:
            'Es tut mir leid, die Konversation konnte nicht gestartet werden. Bitte lade die Seite neu.',
        });
      } finally {
        isInitializingRef.current = false;
      }
    };

    initializeConversation();
  }, [
    topic,
    userData,
    conversationId,
    initialMessageReceived,
    setConversationId,
    setInitialMessageReceived,
    addMessage,
    streamAssistantResponse,
    router,
  ]);

  // Handle user message submission
  const handleSubmit = useCallback(
    async (message: string) => {
      if (!conversationId || isStreaming) return;

      // Add user message
      addMessage({ role: 'user', content: message });

      // Stream assistant response
      await streamAssistantResponse(conversationId, message);
    },
    [conversationId, isStreaming, addMessage, streamAssistantResponse],
  );

  const isLoading = !conversationId || !initialMessageReceived;

  const handleComplete = useCallback(() => {
    setStep('completed');
  }, [setStep]);

  return (
    <section className="relative mx-auto flex size-full max-w-2xl flex-col overflow-hidden">
      <AgentChatMessages scrollRef={scrollRef} isLoading={isLoading} />
      <AgentStreamingIndicator progressMessage={progressMessage} />
      <AgentChatFooter onSubmit={handleSubmit} onComplete={handleComplete} />
    </section>
  );
}
