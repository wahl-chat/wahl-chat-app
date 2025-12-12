import { chatViewScrollToBottom } from '@/lib/scroll-utils';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { areSetsEqual, generateUuid } from '@/lib/utils';
import { toast } from 'sonner';

export const hydrateChatSession: ChatStoreActionHandlerFor<
  'hydrateChatSession'
> =
  (get, set) =>
  async ({
    chatSession,
    chatSessionId,
    messages,
    preSelectedPartyIds,
    initialQuestion,
    userId,
    tenant,
  }) => {
    const {
      chatSessionId: currentChatSessionId,
      partyIds: currentPartyIds,
      loadChatSession,
      initializeChatSession,
    } = get();

    const partyIds = new Set(preSelectedPartyIds ?? []);

    const changedPage =
      chatSessionId !== currentChatSessionId ||
      !areSetsEqual(partyIds, currentPartyIds);

    set((state) => {
      const sessionId = changedPage ? chatSessionId : state.chatSessionId;
      const preliminarySessionId =
        (changedPage ? sessionId : state.localPreliminaryChatSessionId) ??
        generateUuid();

      state.chatSessionId = sessionId;
      state.localPreliminaryChatSessionId = preliminarySessionId;
      state.partyIds = partyIds;
      state.initialQuestionError = undefined;
      state.pendingInitialQuestion = initialQuestion;
      state.userId = userId;
      state.tenant = tenant;
    });

    if (initialQuestion && typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('q');
      window.history.replaceState({}, '', url.toString());
    }

    if (chatSession && messages !== undefined) {
      set((state) => {
        const lastMessage = messages[messages.length - 1];

        return {
          messages,
          chatSessionId: chatSession.id,
          currentQuickReplies: lastMessage
            ? (lastMessage.quick_replies ?? [])
            : [],
          currentChatTitle: chatSession.title,
          chatSessionIsPublic: chatSession.is_public,
          currentStreamingMessages: undefined,
          partyIds: new Set(chatSession.party_ids ?? []),
          preSelectedPartyIds: new Set(chatSession.party_ids ?? []),
          loading: {
            ...state.loading,
            chatSession: false,
            initializingChatSession: false,
            newMessage: false,
          },
          sharingSnapshot: chatSession.sharing_snapshot
            ? {
                id: chatSession.sharing_snapshot?.id,
                messagesLengthAtSharing:
                  chatSession.sharing_snapshot?.messages_length_at_sharing ?? 0,
              }
            : undefined,
        };
      });

      chatViewScrollToBottom();
    } else if (chatSessionId && changedPage) {
      await toast
        .promise(loadChatSession(chatSessionId), {
          loading: 'Loading chat session...',
          success: 'Chat session loaded!',
          error: 'Failed to load chat session',
        })
        .unwrap();
    } else {
      set((state) => ({
        messages: [],
        currentQuickReplies: [],
        currentChatTitle: undefined,
        chatSessionIsPublic: false,
        currentStreamingMessages: undefined,
        loading: {
          ...state.loading,
          chatSession: false,
          initializingChatSession: false,
          newMessage: false,
        },
        sharingSnapshot: undefined,
      }));
    }

    initializeChatSession();
  };
