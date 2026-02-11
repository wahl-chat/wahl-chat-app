import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setSocketConnecting: ChatStoreActionHandlerFor<
  'setSocketConnecting'
> = (get, set) => (isConnecting) => {
  set((state) => {
    state.socket.isConnecting = isConnecting;
  });
};
