import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setPreSelectedParties: ChatStoreActionHandlerFor<
  'setPreSelectedParties'
> = (get, set) => (preSelectedParties) => {
  set({ preSelectedParties });
};
