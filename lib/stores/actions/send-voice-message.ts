import {
  addUserMessageToChatSession,
  createChatSession,
  generateMessageId,
} from '@/lib/firebase/firebase';
import { chatViewScrollToBottom } from '@/lib/scroll-utils';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';
import { Timestamp } from 'firebase/firestore';
import { toast } from 'sonner';

export const sendVoiceMessage: ChatStoreActionHandlerFor<'sendVoiceMessage'> =
  (get, set) => async (audioBase64: string) => {
    const {
      isAnonymous,
      userId,
      chatSessionId,
      localPreliminaryChatSessionId,
      socket,
      partyIds,
      initializeChatSession,
      startTimeoutForStreamingMessages,
    } = get();

    if (!socket.io?.connected) {
      toast.error('wahl.chat ist nicht verbunden.');
      return;
    }

    if (!userId) {
      toast.error('Benutzer nicht authentifiziert.');
      return;
    }

    if (chatSessionId !== localPreliminaryChatSessionId) {
      await initializeChatSession();
    }

    await chatViewScrollToBottom();

    const safeSessionId =
      get().chatSessionId ?? get().localPreliminaryChatSessionId;

    if (!safeSessionId) {
      toast.error('Chat Session out of sync');
      return;
    }

    const voiceMessagePlaceholder = '[Sprachnachricht]';
    const groupedMessageId = generateMessageId(safeSessionId);
    const innerMessageId = generateUuid();

    set((state) => {
      state.messages.push({
        id: groupedMessageId,
        role: 'user',
        messages: [
          {
            id: innerMessageId,
            content: voiceMessagePlaceholder,
            sources: [],
            role: 'user',
            created_at: Timestamp.now(),
          },
        ],
        quick_replies: [],
        created_at: Timestamp.now(),
        voice_transcription: {
          status: 'pending',
        },
      });

      state.input = '';
      state.loading.newMessage = true;
    });

    const messages = get().messages;
    const { tenant } = get();

    try {
      if (messages.length < 2) {
        await createChatSession(
          userId,
          [...partyIds],
          safeSessionId,
          tenant?.id,
        );

        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);

          if (url.pathname === '/session') {
            url.searchParams.set('session_id', safeSessionId);
            window.history.replaceState({}, '', url);
          }
        }
      }

      await addUserMessageToChatSession(
        safeSessionId,
        voiceMessagePlaceholder,
        {
          groupedMessageId: groupedMessageId,
          messageId: innerMessageId,
          voiceTranscription: { status: 'pending' },
        },
      );

      socket.io?.sendVoiceMessage({
        session_id: safeSessionId,
        grouped_message_id: groupedMessageId,
        message_id: innerMessageId,
        audio_base64: audioBase64,
        party_ids: Array.from(partyIds),
        user_is_logged_in: !isAnonymous,
        language: 'de',
      });

      const currentStreamingMessageId = generateUuid();

      set((state) => {
        state.currentStreamingMessages = {
          id: currentStreamingMessageId,
          messages: {},
        };
      });

      startTimeoutForStreamingMessages(currentStreamingMessageId);

      await chatViewScrollToBottom();
    } catch (error) {
      console.error(error);

      set((state) => {
        state.loading.newMessage = false;
        state.error = 'Failed to send voice message';
      });
    }
  };
