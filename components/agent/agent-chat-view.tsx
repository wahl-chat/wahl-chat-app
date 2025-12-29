'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import AgentChatMessage from './agent-chat-message';
import AgentChatInput from './agent-chat-input';
import {
    createConversation,
    streamChatEvents,
    getConversationStage,
} from '@/lib/agent/agent-api';
import { Loader2 } from 'lucide-react';
import AiDisclaimer from '@/components/legal/ai-disclaimer';

export default function AgentChatView() {
    const topic = useAgentStore((state) => state.topic);
    const userData = useAgentStore((state) => state.userData);
    const conversationId = useAgentStore((state) => state.conversationId);
    const messages = useAgentStore((state) => state.messages);
    const isStreaming = useAgentStore((state) => state.isStreaming);
    const initialMessageReceived = useAgentStore(
        (state) => state.initialMessageReceived
    );

    const setConversationId = useAgentStore((state) => state.setConversationId);
    const setConversationStage = useAgentStore((state) => state.setConversationStage);
    const addMessage = useAgentStore((state) => state.addMessage);
    const setIsStreaming = useAgentStore((state) => state.setIsStreaming);
    const setInitialMessageReceived = useAgentStore(
        (state) => state.setInitialMessageReceived
    );
    const updateLastAssistantMessage = useAgentStore(
        (state) => state.updateLastAssistantMessage
    );

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

            try {
                let currentContent = '';

                for await (const event of streamChatEvents(convId, userMessage)) {
                    if (event.type === 'message_start') {
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
                        'Es tut mir leid, es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.',
                });
            } finally {
                setIsStreaming(false);
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
                console.log('Creating conversation...');
                const response = await createConversation(topic, userData);
                setConversationId(response.conversation_id);
                console.log('Created Conversation ID:', response.conversation_id);

                // Get initial message from assistant (empty user message triggers it)
                await streamAssistantResponse(response.conversation_id, '');
                setInitialMessageReceived(true);
            } catch (error) {
                console.error('Error initializing conversation:', error);
                addMessage({
                    role: 'assistant',
                    content:
                        'Es tut mir leid, die Konversation konnte nicht gestartet werden. Bitte laden Sie die Seite neu.',
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
                    Thema: <span className="font-medium text-foreground">{topic}</span>
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

            {/* Streaming indicator */}
            {isStreaming && (
                <div className="shrink-0 px-4 pb-2">
                    <p className="text-center text-xs text-muted-foreground">
                        Der Wahl Agent denkt nach...
                    </p>
                </div>
            )}

            {/* Input */}
            <div className="shrink-0 px-3 pb-3 md:px-4 md:pb-4">
                <AgentChatInput onSubmit={handleSubmit} />
                <AiDisclaimer />
            </div>
        </section>
    );
}


