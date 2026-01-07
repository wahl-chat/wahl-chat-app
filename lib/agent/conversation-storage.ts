const STORAGE_KEY = 'wahl-agent-conversation';

export interface StoredConversation {
    conversationId: string;
    timestamp: number;
}

/**
 * Saves the current conversation ID to localStorage
 */
export function saveConversationId(conversationId: string): void {
    if (typeof window === 'undefined') return;

    const data: StoredConversation = {
        conversationId,
        timestamp: Date.now(),
    };

    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (error) {
        console.error('Failed to save conversation to localStorage:', error);
    }
}

/**
 * Retrieves the stored conversation ID from localStorage
 */
export function getStoredConversationId(): string | null {
    if (typeof window === 'undefined') return null;

    try {
        const data = localStorage.getItem(STORAGE_KEY);
        if (!data) return null;

        const parsed: StoredConversation = JSON.parse(data);
        return parsed.conversationId;
    } catch (error) {
        console.error('Failed to read conversation from localStorage:', error);
        return null;
    }
}

/**
 * Clears the stored conversation from localStorage
 */
export function clearStoredConversation(): void {
    if (typeof window === 'undefined') return;

    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
        console.error('Failed to clear conversation from localStorage:', error);
    }
}