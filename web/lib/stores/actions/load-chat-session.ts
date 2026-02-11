import {
  getChatSession,
  getChatSessionMessages,
} from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const loadChatSession: ChatStoreActionHandlerFor<'loadChatSession'> =
  (get, set) => async (chatSessionId) => {
    set((state) => {
      state.loading.chatSession = true;
      state.error = undefined;
      state.chatSessionId = chatSessionId;
    });

    try {
      const session = await getChatSession(chatSessionId);
      const messages = await getChatSessionMessages(chatSessionId);

      return set((state) => ({
        messages,
        currentQuickReplies:
          messages.length > 0
            ? (messages[messages.length - 1].quick_replies ?? [])
            : [],
        currentChatTitle: session.title,
        chatSessionIsPublic: session.is_public,
        partyIds: new Set(session.party_ids ?? []),
        preSelectedPartyIds: new Set(session.party_ids ?? []),
        currentStreamingMessages: undefined,
        loading: {
          ...state.loading,
          chatSession: false,
          initializingChatSession: false,
          newMessage: false,
        },
        sharingSnapshot: session.sharing_snapshot
          ? {
              id: session.sharing_snapshot.id,
              messagesLengthAtSharing:
                session.sharing_snapshot.messages_length_at_sharing,
            }
          : undefined,
      }));
    } catch (error) {
      console.error(error);

      set((state) => {
        state.loading.chatSession = false;
        state.loading.newMessage = false;
        state.error = 'Failed to load chat session';
        state.messages = [];
      });

      return Promise.reject(error);
    }
  };
