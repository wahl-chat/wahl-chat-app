import { updateChatSession } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setChatSessionIsPublic: ChatStoreActionHandlerFor<
  'setChatSessionIsPublic'
> = (get, set) => async (isPublic) => {
  const { chatSessionId } = get();

  if (!chatSessionId) return;

  await updateChatSession(chatSessionId, {
    is_public: isPublic,
  });

  return set({ chatSessionIsPublic: isPublic });
};
