import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setInput: ChatStoreActionHandlerFor<'setInput'> =
  (_, set) => (input) => {
    set({ input });
  };
