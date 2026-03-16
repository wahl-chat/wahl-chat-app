import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  addUserMessageToChatSession,
  createChatSession,
} from '@/lib/firebase/firebase';
import {
  incrementWahlChatSessionMessageCount,
  isProlificStudy,
} from '@/lib/prolific-study/prolific-metadata';
import { chatViewScrollToBottom } from '@/lib/scroll-utils';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';
import { Timestamp } from 'firebase/firestore';
import { toast } from 'sonner';

export const chatAddUserMessage: ChatStoreActionHandlerFor<'addUserMessage'> =
  (get, set) =>
  async (userId: string, message: string, fromInitialQuestion?: boolean) => {
    const {
      isAnonymous,
      chatSessionId,
      contextId,
      localPreliminaryChatSessionId,
      socket,
      partyIds,
      initializeChatSession,
      startTimeoutForStreamingMessages,
      prolificMetadata,
      incrementProlificMessageCount,
    } = get();

    const safeContextId = contextId ?? DEFAULT_CONTEXT_ID;

    if (!socket.io?.connected) {
      if (!fromInitialQuestion) toast.error('wahl.chat ist nicht verbunden.');
      else
        set((state) => {
          state.initialQuestionError = message;
        });

      return;
    }

    if (chatSessionId !== localPreliminaryChatSessionId) {
      initializeChatSession();
    }

    chatViewScrollToBottom();

    const safeSessionId =
      get().chatSessionId ?? get().localPreliminaryChatSessionId;

    if (!safeSessionId) {
      toast.error('Chat Session out of sync');

      return;
    }

    let messages = get().messages;
    const lastMessage = messages[messages.length - 1];
    const isMessageResend =
      messages.length > 0 &&
      lastMessage.role === 'user' &&
      lastMessage.messages[0].content === message;

    set((state) => {
      if (!isMessageResend) {
        state.messages.push({
          id: generateUuid(),
          role: 'user',
          messages: [
            {
              id: generateUuid(),
              content: message,
              sources: [],
              role: 'user',
              created_at: Timestamp.now(),
            },
          ],
          quick_replies: [],
          created_at: Timestamp.now(),
        });

        state.input = '';
      }
      state.loading.newMessage = true;
    });

    if (!isMessageResend && isProlificStudy()) {
      incrementWahlChatSessionMessageCount(); // increment in session storage
      incrementProlificMessageCount(); // increment store for reactivity
    }

    messages = get().messages;
    const { tenant } = get();

    try {
      if (messages.length < 2 && !isMessageResend) {
        await createChatSession(
          userId,
          [...partyIds],
          safeSessionId,
          tenant?.id,
          safeContextId,
          prolificMetadata,
        );

        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);

          // Check if we're on a session page (context-specific or legacy)
          if (
            url.pathname.endsWith('/session') ||
            url.pathname === '/session'
          ) {
            url.searchParams.set('session_id', safeSessionId);
            window.history.replaceState({}, '', url);
          }
        }
      }

      if (!isMessageResend) {
        await addUserMessageToChatSession(safeSessionId, message);
      }

      socket.io?.addUserMessage({
        session_id: safeSessionId,
        context_id: safeContextId,
        user_message: message,
        party_ids: Array.from(partyIds),
        user_is_logged_in: !isAnonymous,
      });

      const currentStreamingMessageId = generateUuid();

      set((state) => {
        state.currentStreamingMessages = {
          id: currentStreamingMessageId,
          messages: {},
        };

        state.initialQuestionError = undefined;
        state.pendingInitialQuestion = undefined;
      });

      startTimeoutForStreamingMessages(currentStreamingMessageId);

      chatViewScrollToBottom();
    } catch (error) {
      console.error(error);

      set((state) => {
        state.loading.newMessage = false;
        state.error = 'Failed to get chat answer';
      });
    }
  };
