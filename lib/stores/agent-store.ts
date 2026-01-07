'use client';

import { createStore } from 'zustand/vanilla';
import { generateUuid } from '@/lib/utils';

// Types
export type AgentStep =
    | 'consent'
    | 'conversation-choice'
    | 'data-collection'
    | 'topic-selection'
    | 'chat'
    | 'completed';

export type AgentTopic = 'Migration' | 'Wirtschaft' | 'Umwelt und Klima';

export type ConversationStage =
    | 'start'
    | 'active_listening'
    | 'party_positioning'
    | 'perspective_taking'
    | 'deliberation'
    | 'party_matching'
    | 'end';

export const CONVERSATION_STAGES: ConversationStage[] = [
    'start',
    'active_listening',
    'party_positioning',
    'perspective_taking',
    'deliberation',
    'party_matching',
    'end',
];

export const STAGE_LABELS: Record<ConversationStage, string> = {
    start: 'Start',
    active_listening: 'Aktives Zuhören',
    party_positioning: 'Partei-Positionierung',
    perspective_taking: 'Perspektivwechsel',
    deliberation: 'Deliberation',
    party_matching: 'Partei-Matching',
    end: 'Abschluss',
};

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
    conversationStage: ConversationStage | null;
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
    startNewConversation: () => void;
    restoreConversation: (
        conversationId: string,
        messages: Array<{ role: 'user' | 'assistant'; content: string }>,
        topic: AgentTopic,
        stage: ConversationStage
    ) => void;

    // User data actions
    setUserData: (data: AgentUserData) => void;
    setTopic: (topic: AgentTopic) => void;

    // Conversation actions
    setConversationId: (id: string) => void;
    setConversationStage: (stage: ConversationStage) => void;
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
    conversationStage: null,
    messages: [],
    isStreaming: false,
    pendingUserMessage: null,
    initialMessageReceived: false,
    input: '',
};

export const createAgentStore = (initState: Partial<AgentState> = {}) => {
    return createStore<AgentStore>()((set) => ({
        ...initialState,
        ...initState,

        // Flow actions
        setStep: (step) => set({ step }),

        giveConsent: () =>
            set({
                consentGiven: true,
                step: 'conversation-choice',
            }),

        startNewConversation: () =>
            set({
                step: 'data-collection',
            }),

        restoreConversation: (conversationId, messages, topic, stage) =>
            set({
                conversationId,
                messages: messages.map((msg) => ({
                    ...msg,
                    id: generateUuid(),
                })),
                topic,
                conversationStage: stage,
                initialMessageReceived: true,
                step: 'chat',
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

        setConversationStage: (conversationStage) => set({ conversationStage }),

        addMessage: (message) =>
            set((state) => ({
                messages: [
                    ...state.messages,
                    { ...message, id: generateUuid() },
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
