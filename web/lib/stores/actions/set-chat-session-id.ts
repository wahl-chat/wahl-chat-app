import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setChatSessionId: ChatStoreActionHandlerFor<'setChatSessionId'> =
  (get, set) => (chatSessionId) => {
    set({ chatSessionId });
  };
