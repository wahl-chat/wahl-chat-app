import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setSocket: ChatStoreActionHandlerFor<'setSocket'> =
  (get, set) => (socket) => {
    set((state) => ({
      socket: {
        ...state.socket,
        io: socket,
      },
    }));
  };
