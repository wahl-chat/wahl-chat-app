import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setSocketConnected: ChatStoreActionHandlerFor<
  'setSocketConnected'
> = (get, set) => (connected) => {
  const { initializeChatSession, cancelStreamingMessages } = get();

  if (connected) {
    initializeChatSession();
  } else {
    cancelStreamingMessages();
  }

  set((state) => {
    state.socket.connected = connected;
  });
};
