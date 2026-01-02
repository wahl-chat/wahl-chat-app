import type { AgentUserData, AgentTopic, ConversationStage } from '@/lib/stores/agent-store';

// Use Next.js API routes as proxy to avoid CORS issues
const API_BASE_URL = '/api/agent';

export interface CreateConversationResponse {
    conversation_id: string;
}

export interface ConversationStageResponse {
    stage: ConversationStage;
}

export interface ConversationMessagesResponse {
    messages: Array<{
        role: string;
        content: string;
    }>;
}

export interface ConversationTopicResponse {
    topic: AgentTopic;
}

export interface StreamEvent {
    type: 'message_start' | 'message_chunk' | 'message_end' | 'end';
    content?: string;
}

/**
 * Creates a new conversation with the agent backend
 */
export async function createConversation(
    topic: AgentTopic,
    userData: AgentUserData
): Promise<CreateConversationResponse> {
    const response = await fetch(`${API_BASE_URL}/chat-start`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            topic,
            age: userData.age,
            region: userData.region,
            living_situation: userData.livingSituation,
            occupation: userData.occupation,
        }),
    });

    if (!response.ok) {
        throw new Error(`Failed to create conversation: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Streams chat events from the agent backend
 * Returns an async generator that yields StreamEvent objects
 */
export async function* streamChatEvents(
    conversationId: string,
    userMessage: string
): AsyncGenerator<StreamEvent> {
    const response = await fetch(`${API_BASE_URL}/chat-stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            conversation_id: conversationId,
            user_message: userMessage,
        }),
    });

    if (!response.ok) {
        throw new Error(`Failed to stream chat: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
        throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete lines (NDJSON format)
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.trim()) continue;

                try {
                    const event = JSON.parse(line) as StreamEvent;
                    yield event;

                    if (event.type === 'end') {
                        return;
                    }
                } catch {
                    // Skip invalid JSON lines
                    console.warn('Invalid JSON in stream:', line);
                }
            }
        }

        // Process any remaining content in buffer
        if (buffer.trim()) {
            try {
                const event = JSON.parse(buffer) as StreamEvent;
                yield event;
            } catch {
                console.warn('Invalid JSON in final buffer:', buffer);
            }
        }
    } finally {
        reader.releaseLock();
    }
}

/**
 * Fetches the current conversation stage from the backend
 */
export async function getConversationStage(
    conversationId: string
): Promise<ConversationStageResponse> {
    const response = await fetch(`${API_BASE_URL}/conversation-stage/${conversationId}`, {
        method: 'GET',
    });

    if (!response.ok) {
        throw new Error(`Failed to get conversation stage: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Fetches all messages for a conversation from the backend
 */
export async function getConversationMessages(
    conversationId: string
): Promise<ConversationMessagesResponse> {
    const response = await fetch(`${API_BASE_URL}/conversation-messages/${conversationId}`, {
        method: 'GET',
    });

    if (!response.ok) {
        throw new Error(`Failed to get conversation messages: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Fetches the topic for a conversation from the backend
 */
export async function getConversationTopic(
    conversationId: string
): Promise<ConversationTopicResponse> {
    const response = await fetch(`${API_BASE_URL}/conversation-topic/${conversationId}`, {
        method: 'GET',
    });

    if (!response.ok) {
        throw new Error(`Failed to get conversation topic: ${response.statusText}`);
    }

    return response.json();
}
