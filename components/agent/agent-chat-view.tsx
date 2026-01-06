'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import AgentChatMessage from './agent-chat-message';
import AgentChatInput from './agent-chat-input';
import {
    createConversation,
    streamChatEvents,
    getConversationStage,
} from '@/lib/agent/agent-api';
import { saveConversationId } from '@/lib/agent/conversation-storage';
import { Loader2, CheckCircle2 } from 'lucide-react';
import AiDisclaimer from '@/components/legal/ai-disclaimer';
import { Button } from '@/components/ui/button';

export default function AgentChatView() {
    const router = useRouter();

    const topic = useAgentStore((state) => state.topic);
    const userData = useAgentStore((state) => state.userData);
    const conversationId = useAgentStore((state) => state.conversationId);
    const conversationStage = useAgentStore((state) => state.conversationStage);
    const messages = useAgentStore((state) => state.messages);
    const isStreaming = useAgentStore((state) => state.isStreaming);
    const initialMessageReceived = useAgentStore(
        (state) => state.initialMessageReceived
    );

    const setConversationId = useAgentStore((state) => state.setConversationId);
    const setConversationStage = useAgentStore((state) => state.setConversationStage);
    const setStep = useAgentStore((state) => state.setStep);
    const addMessage = useAgentStore((state) => state.addMessage);
    const setIsStreaming = useAgentStore((state) => state.setIsStreaming);
    const setInitialMessageReceived = useAgentStore(
        (state) => state.setInitialMessageReceived
    );
    const updateLastAssistantMessage = useAgentStore(
        (state) => state.updateLastAssistantMessage
    );

    const isConversationEnded = conversationStage === 'end';

    const [progressMessage, setProgressMessage] = useState<string | null>(null);

    const scrollRef = useRef<HTMLDivElement>(null);
    const isInitializingRef = useRef(false);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

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
        [setConversationStage]
    );

    // Stream assistant response
    const streamAssistantResponse = useCallback(
        async (convId: string, userMessage: string) => {
            setIsStreaming(true);
            setProgressMessage(null);

            try {
                let currentContent = '';

                for await (const event of streamChatEvents(convId, userMessage)) {
                    if (event.type === 'progress_update' && event.content) {
                        setProgressMessage(event.content);
                    } else if (event.type === 'message_start') {
                        setProgressMessage(null);
                        addMessage({ role: 'assistant', content: '' });
                        currentContent = '';
                    } else if (event.type === 'message_chunk' && event.content) {
                        currentContent += event.content;
                        updateLastAssistantMessage(currentContent);
                    } else if (event.type === 'message_end') {
                        // Message complete
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
        [addMessage, setIsStreaming, updateLastAssistantMessage, fetchConversationStage]
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
        [conversationId, isStreaming, addMessage, streamAssistantResponse]
    );

    const isLoading = !conversationId || !initialMessageReceived;

    return (
        <section className="relative mx-auto flex size-full max-w-2xl flex-col overflow-hidden">
            {/* Topic indicator */}
            <div className="shrink-0 px-4 py-2">
                <p className="text-center text-sm text-muted-foreground">
                    Konversation über: <span className="font-medium text-foreground">{topic}</span>
                </p>
            </div>

            {/* Messages */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto scroll-smooth px-4 py-4"
            >
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

            {/* Streaming indicator - always rendered to prevent layout shift */}
            <div className="h-8 shrink-0 px-4">
                {isStreaming && (
                    <p className="text-center text-sm text-muted-foreground">
                        {progressMessage ?? 'Der Wahl Agent denkt nach'}
                        <span className="ml-0.5 inline-flex gap-0.5 align-baseline">
                            <span className="inline-block size-1 animate-typing-dot rounded-full bg-muted-foreground" style={{ animationDelay: '0ms' }} />
                            <span className="inline-block size-1 animate-typing-dot rounded-full bg-muted-foreground" style={{ animationDelay: '200ms' }} />
                            <span className="inline-block size-1 animate-typing-dot rounded-full bg-muted-foreground" style={{ animationDelay: '400ms' }} />
                        </span>
                    </p>
                )}
            </div>

            {/* Input or Completion Button */}
            <div className="shrink-0 px-3 pb-3 md:px-4 md:pb-4">
                {isConversationEnded ? (
                    <Button
                        onClick={() => setStep('completed')}
                        className="w-full gap-2"
                        size="lg"
                    >
                        <CheckCircle2 className="size-4" />
                        Gespräch abschließen
                    </Button>
                ) : (
                    <AgentChatInput onSubmit={handleSubmit} />
                )}
                <AiDisclaimer />
            </div>
        </section>
    );
}


