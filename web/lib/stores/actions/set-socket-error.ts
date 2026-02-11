import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setSocketError: ChatStoreActionHandlerFor<'setSocketError'> =
  (get, set) => (error) => {
    set((state) => {
      state.socket.error = error;
    });
  };
