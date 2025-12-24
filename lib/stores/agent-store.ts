'use client';

import { createStore } from 'zustand/vanilla';

// Types
export type AgentStep =
    | 'consent'
    | 'data-collection'
    | 'topic-selection'
    | 'chat'
    | 'completed';

export type AgentTopic = 'Migration' | 'Wirtschaft' | 'Umwelt und Klima';

export interface AgentUserData {
    age: number;
    region: string;
    livingSituation: string;
    occupation: string;
}

export interface AgentMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
}

export interface AgentState {
    // Flow state
    step: AgentStep;
    consentGiven: boolean;

    // User data
    userData: AgentUserData | null;
    topic: AgentTopic | null;

    // Conversation
    conversationId: string | null;
    messages: AgentMessage[];
    isStreaming: boolean;
    pendingUserMessage: string | null;
    initialMessageReceived: boolean;

    // Input
    input: string;
}

export interface AgentActions {
    // Flow actions
    setStep: (step: AgentStep) => void;
    giveConsent: () => void;

    // User data actions
    setUserData: (data: AgentUserData) => void;
    setTopic: (topic: AgentTopic) => void;

    // Conversation actions
    setConversationId: (id: string) => void;
    addMessage: (message: Omit<AgentMessage, 'id'>) => void;
    setIsStreaming: (isStreaming: boolean) => void;
    setPendingUserMessage: (message: string | null) => void;
    setInitialMessageReceived: (received: boolean) => void;
    updateLastAssistantMessage: (content: string) => void;

    // Input actions
    setInput: (input: string) => void;

    // Reset
    reset: () => void;
}

export type AgentStore = AgentState & AgentActions;

const initialState: AgentState = {
    step: 'consent',
    consentGiven: false,
    userData: null,
    topic: null,
    conversationId: null,
    messages: [],
    isStreaming: false,
    pendingUserMessage: null,
    initialMessageReceived: false,
    input: '',
};

export const createAgentStore = (initState: Partial<AgentState> = {}) => {
    return createStore<AgentStore>()((set, get) => ({
        ...initialState,
        ...initState,

        // Flow actions
        setStep: (step) => set({ step }),

        giveConsent: () =>
            set({
                consentGiven: true,
                step: 'data-collection',
            }),

        // User data actions
        setUserData: (userData) =>
            set({
                userData,
                step: 'topic-selection',
            }),

        setTopic: (topic) =>
            set({
                topic,
                step: 'chat',
            }),

        // Conversation actions
        setConversationId: (conversationId) => set({ conversationId }),

        addMessage: (message) =>
            set((state) => ({
                messages: [
                    ...state.messages,
                    { ...message, id: `msg-${Date.now()}-${Math.random()}` },
                ],
            })),

        setIsStreaming: (isStreaming) => set({ isStreaming }),

        setPendingUserMessage: (pendingUserMessage) => set({ pendingUserMessage }),

        setInitialMessageReceived: (initialMessageReceived) =>
            set({ initialMessageReceived }),

        updateLastAssistantMessage: (content) =>
            set((state) => {
                const messages = [...state.messages];
                const lastIndex = messages.length - 1;
                if (lastIndex >= 0 && messages[lastIndex].role === 'assistant') {
                    messages[lastIndex] = { ...messages[lastIndex], content };
                }
                return { messages };
            }),

        // Input actions
        setInput: (input) => set({ input }),

        // Reset
        reset: () => set(initialState),
    }));
};

