import { updateRelatedItemsOfMessage } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

/** Feed items matching the turn's question, shown under its answer. */
export const setRelatedItems: ChatStoreActionHandlerFor<'setRelatedItems'> =
  (get, set) => async (sessionId, itemIds) => {
    const { chatSessionId, messages } = get();
    if (!chatSessionId || chatSessionId !== sessionId || itemIds.length === 0) {
      return;
    }
    const index = messages.length - 1;
    const last = messages[index];
    if (!last || last.role !== 'assistant') return;

    set((state) => {
      state.messages[index].related_item_ids = itemIds;
    });
    try {
      await updateRelatedItemsOfMessage(chatSessionId, last.id, itemIds);
    } catch (error) {
      console.error('Failed to store the related feed items', error);
    }
  };
