import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const newChat: ChatStoreActionHandlerFor<'newChat'> =
  (get, set) => () => {
    set({
      chatSessionId: undefined,
      messages: [],
      // The new chat's answers have not been counted yet. studyAnswersCompleted
      // deliberately survives: it counts the participant, not the chat.
      sessionAnswersCounted: 0,
      input: '',
      error: undefined,
      currentQuickReplies: [],
      currentChatTitle: undefined,
    });
  };
