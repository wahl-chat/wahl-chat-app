import { getSseChatAppend } from '@/components/providers/sse-chat-provider';
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
      chatSessionId,
      contextId,
      localPreliminaryChatSessionId,
      partyIds,
      messages: currentMessages,
      prolificMetadata,
      incrementProlificMessageCount,
      startTimeoutForStreamingMessages,
    } = get();

    const safeContextId = contextId ?? DEFAULT_CONTEXT_ID;

    // Reject concurrent sends: AI SDK v5 does not serialize a second
    // sendMessage — it REPLACES the active response, so trailing events from
    // the running turn would be aborted or applied to the wrong turn. The turn
    // stays busy until the stream is terminal (onFinish / error paths).
    if (get().loading.newMessage) {
      toast.error('Bitte warte, bis die aktuelle Antwort abgeschlossen ist.');
      return;
    }

    // SSE model: no socket connectivity check needed — each message is a fresh
    // HTTP POST. There is no persistent connection to be "connected" to.

    chatViewScrollToBottom();

    const safeSessionId = chatSessionId ?? localPreliminaryChatSessionId;

    if (!safeSessionId) {
      if (!fromInitialQuestion) {
        toast.error('Chat Session out of sync');
      } else {
        set((state) => {
          state.initialQuestionError = message;
        });
      }

      return;
    }

    // SSE: the backend echoes `session_id` in every streamed event, and the
    // store gates event handlers (selectRespondingParties, completeStreamingMessage,
    // ...) on `chatSessionId === session_id`. We send `safeSessionId` (which falls
    // back to localPreliminaryChatSessionId), but nothing in the SSE flow promotes
    // it to `chatSessionId` (the old socket init did). Set it here so events match.
    if (chatSessionId !== safeSessionId) {
      set((state) => {
        state.chatSessionId = safeSessionId;
      });
    }

    let messages = currentMessages;
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
      // Firebase writes — NOT Socket.IO; must be preserved.
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

      // Build chat_history for the stateless SSE request
      // (client sends full history each request).
      const chatHistory = messages.flatMap((m) =>
        m.messages.map((innerMessage) => ({
          ...innerMessage,
          role: innerMessage.role,
          created_at: m.created_at,
          quick_replies: m.quick_replies,
        })),
      );

      // SSE replacement: call useChat append() exposed from
      // sse-chat-provider via getSseChatAppend() (SSE-03).
      const appendMessage = getSseChatAppend();
      if (!appendMessage) {
        // User-visible feedback via toast — the old `state.error` write was
        // dead (no component renders it).
        toast.error(
          'Der Chat ist noch nicht bereit. Bitte lade die Seite neu.',
        );
        set((state) => {
          state.loading.newMessage = false;
        });
        return;
      }

      appendMessage(
        { role: 'user', content: message },
        {
          session_id: safeSessionId,
          context_id: safeContextId,
          party_ids: Array.from(partyIds),
          chat_history: chatHistory,
        },
      );

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

      // User-visible feedback via toast — the old `state.error` write was
      // dead (no component renders it).
      toast.error(
        'Die Antwort konnte nicht geladen werden. Bitte versuche es erneut.',
      );
      set((state) => {
        state.loading.newMessage = false;
      });
    }
  };
