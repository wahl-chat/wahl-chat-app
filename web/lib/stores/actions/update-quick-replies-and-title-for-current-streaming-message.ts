import {
  updateQuickRepliesOfMessage,
  updateTitleOfMessage,
} from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const updateQuickRepliesAndTitleForCurrentStreamingMessage: ChatStoreActionHandlerFor<
  'updateQuickRepliesAndTitleForCurrentStreamingMessage'
> = (get, set) => async (sessionId, quickReplies, title) => {
  const { chatSessionId, messages } = get();

  if (!chatSessionId) return;
  if (chatSessionId !== sessionId) {
    await updateTitleOfMessage(sessionId, title);

    return;
  }

  const lastMessage = messages[messages.length - 1];

  set((state) => {
    state.loading.newMessage = false;
    state.currentQuickReplies = quickReplies;
    state.currentChatTitle = title;
  });

  await Promise.all([
    updateQuickRepliesOfMessage(chatSessionId, lastMessage.id, quickReplies),
    updateTitleOfMessage(chatSessionId, title),
  ]);
};
