import { updateChatSession } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setPartyIds: ChatStoreActionHandlerFor<'setPartyIds'> =
  (get, set) => async (partyIds: string[]) => {
    set((state) => {
      state.partyIds = new Set([...partyIds]);
    });

    // A chat without messages has no session doc yet; its first message
    // creates one with these parties.
    const { chatSessionId, messages } = get();
    if (!chatSessionId || messages.length === 0) return;

    try {
      await updateChatSession(chatSessionId, {
        party_ids: Array.from(get().partyIds),
      });
    } catch (error) {
      console.error('Failed to store the chat parties', error);
    }
  };
